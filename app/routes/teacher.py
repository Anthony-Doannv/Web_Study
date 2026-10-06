from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
import re
from flask_login import login_required, current_user
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import User, Lesson, Exercise, Test, Submission, SupportRequest, Subject
from ..services.ai_quiz import AIUnavailable, generate_quick_quiz, generate_exercise_quiz
from ..services.subject_order import sort_subjects

teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')


SUPPORT_STATUS_LABELS = {
    'pending': 'Chờ xử lý',
    'in_progress': 'Đang xử lý',
    'done': 'Đã hoàn thành',
}




TEST_TYPE_LABELS = {
    'chapter': 'Kiểm tra theo chương',
    'midterm_hk1': 'Giữa học kì 1',
    'midterm_hk2': 'Giữa học kì 2',
    'final_hk1': 'Cuối học kì 1',
    'final_hk2': 'Cuối học kì 2',
    'term': 'Kiểu cũ (term)',
}


def _display_test_type(test):
    test_type = (test.test_type or '').lower()
    title = (test.title or '').lower()
    if test_type == 'chapter':
        return f'Chương {test.chapter}' if test.chapter else 'Theo chương'
    if test_type == 'term':
        if 'giữa' in title and ('1' in title or 'i 1' in title):
            return 'Giữa học kì 1'
        if 'giữa' in title and ('2' in title or 'i 2' in title):
            return 'Giữa học kì 2'
        if 'cuối' in title and ('1' in title or 'i 1' in title):
            return 'Cuối học kì 1'
        if 'cuối' in title and ('2' in title or 'i 2' in title):
            return 'Cuối học kì 2'
    return TEST_TYPE_LABELS.get(test_type, test_type or '-')


def _default_test_title(subject_name, test_type, chapter=None):
    mapping = {
        'chapter': f'Kiểm tra chương {chapter} - {subject_name}' if chapter else f'Kiểm tra chương - {subject_name}',
        'midterm_hk1': f'Kiểm tra giữa học kì 1 - {subject_name}',
        'midterm_hk2': f'Kiểm tra giữa học kì 2 - {subject_name}',
        'final_hk1': f'Kiểm tra cuối học kì 1 - {subject_name}',
        'final_hk2': f'Kiểm tra cuối học kì 2 - {subject_name}',
        'term': f'Kiểm tra học kì - {subject_name}',
    }
    return mapping.get(test_type, f'Bài kiểm tra - {subject_name}')




def _preview_difficulty(index: int, total: int) -> str:
    if total <= 0:
        return 'Trung bình'
    ratio = index / total
    if ratio <= 0.3:
        return 'Dễ'
    if ratio <= 0.75:
        return 'Trung bình'
    return 'Khó'


def _build_answer_preview_payload(questions, label, title, back_url, answer_note=None, source_note=None, summary=None):
    normalized = []
    total = len(questions)
    for idx, q in enumerate(questions, start=1):
        question_text = re.sub(r'^\s*Câu\s*\d+\s*[:.-]?\s*', '', (q.get('question') or '').strip(), flags=re.I)
        normalized.append({
            'index': idx,
            'question': question_text,
            'options': q.get('options', [])[:4],
            'answer': (q.get('answer') or '').strip().upper()[:1],
            'difficulty': (q.get('difficulty') or '').strip() or _preview_difficulty(idx, total),
            'explanation': (q.get('explanation') or '').strip(),
        })
    return render_template(
        'teacher/answer_preview.html',
        label=label,
        title=title,
        questions=normalized,
        back_url=back_url,
        answer_note=answer_note,
        source_note=source_note,
        summary=summary or {},
    )


def _clean_question_text(text: str) -> str:
    return re.sub(r'^\s*Câu\s*\d+\s*[:.-]?\s*', '', (text or '').strip(), flags=re.I).strip()


def _normalize_editor_question(raw_question: dict, index: int, total: int) -> dict:
    options = [str(x or '').strip() for x in (raw_question.get('options') or [])[:4]]
    while len(options) < 4:
        options.append(f'Phương án {chr(65 + len(options))}')
    answer = (raw_question.get('answer') or '').strip().upper()[:1]
    if answer not in {'A', 'B', 'C', 'D'}:
        answer = 'A'
    difficulty = (raw_question.get('difficulty') or '').strip() or _preview_difficulty(index, total)
    return {
        'question': _clean_question_text(raw_question.get('question', '')),
        'options': options,
        'answer': answer,
        'difficulty': difficulty,
        'explanation': (raw_question.get('explanation') or '').strip(),
    }


def _prepare_editor_questions(questions: list[dict]) -> list[dict]:
    total = len(questions)
    return [_normalize_editor_question(question, idx, total) for idx, question in enumerate(questions, start=1)]


def _extract_questions_from_form() -> list[dict]:
    count = request.form.get('question_count', type=int) or 0
    questions = []
    total = max(count, 1)
    for idx in range(count):
        question_text = request.form.get(f'question_{idx}', '').strip()
        options = [request.form.get(f'option_{idx}_{opt}', '').strip() for opt in range(4)]
        explanation = request.form.get(f'explanation_{idx}', '').strip()
        difficulty = request.form.get(f'difficulty_{idx}', '').strip()
        answer = (request.form.get(f'answer_{idx}') or 'A').strip().upper()[:1]
        if not question_text and not any(options):
            continue
        questions.append(_normalize_editor_question({
            'question': question_text,
            'options': options,
            'answer': answer,
            'difficulty': difficulty,
            'explanation': explanation,
        }, len(questions) + 1, total))
    return questions


def _exercise_editor_questions(item: Exercise, commit_if_missing: bool = False) -> list[dict]:
    stored = item.get_question_bank()
    if not stored:
        try:
            stored = generate_exercise_quiz(
                item.subject.name if item.subject else 'môn học',
                item.title, item.content, item.grade_level, item.chapter, count=12,
            )
        except AIUnavailable:
            flash('AI đang bận, chưa tạo được câu hỏi. Bạn có thể tự nhập câu hỏi hoặc thử lại sau.', 'warning')
            return []
        item.set_question_bank(stored)
        if commit_if_missing:
            db.session.commit()
    return _prepare_editor_questions(item.get_question_bank())


def _test_editor_questions(item: Test) -> list[dict]:
    return _prepare_editor_questions(item.get_question_bank())

def _ensure_teacher():
    if not current_user.is_authenticated:
        abort(401)
    if getattr(current_user, 'role', None) not in ['teacher', 'admin']:
        abort(403)


def _student_query():
    return User.query.filter(User.role == 'student')


def _student_choices():
    return _student_query().order_by(User.grade_level.asc(), User.class_name.asc(), User.full_name.asc()).all()


def _subjects():
    return sort_subjects(Subject.query.all())


def _teacher_learning_metrics():
    students = _student_choices()
    submissions = Submission.query.options(
        joinedload(Submission.user),
        joinedload(Submission.test).joinedload(Test.subject),
        joinedload(Submission.exercise).joinedload(Exercise.subject),
    ).all()

    grade_counts = {str(g): 0 for g in range(6, 13)}
    for student in students:
        if student.grade_level:
            grade_counts[str(student.grade_level)] = grade_counts.get(str(student.grade_level), 0) + 1

    avg_score_by_grade = []
    for grade in range(6, 13):
        grade_subs = [sub for sub in submissions if sub.user and sub.user.grade_level == grade and sub.score is not None]
        avg = round(sum((sub.score or 0) for sub in grade_subs) / len(grade_subs), 2) if grade_subs else 0
        avg_score_by_grade.append({'grade': grade, 'avg': avg})

    subject_submission_counts = []
    avg_score_by_subject = []
    for subject in _subjects():
        subject_subs = []
        for sub in submissions:
            target_subject_id = None
            if sub.test and sub.test.subject_id:
                target_subject_id = sub.test.subject_id
            elif sub.exercise and sub.exercise.subject_id:
                target_subject_id = sub.exercise.subject_id
            if target_subject_id == subject.id:
                subject_subs.append(sub)
        subject_submission_counts.append({'name': subject.name, 'count': len(subject_subs)})
        avg = round(sum((sub.score or 0) for sub in subject_subs) / len(subject_subs), 2) if subject_subs else 0
        avg_score_by_subject.append({'name': subject.name, 'avg': avg})

    return {
        'grade_counts': grade_counts,
        'avg_score_by_grade': avg_score_by_grade,
        'avg_score_by_subject': avg_score_by_subject,
        'subject_submission_counts': subject_submission_counts,
    }


@teacher_bp.before_request
@login_required
def check_teacher_role():
    _ensure_teacher()


@teacher_bp.route('/dashboard')
def dashboard():
    students = _student_choices()
    stats = {
        'Học viên': len(students),
        'Bài học': Lesson.query.count(),
        'Bài tập': Exercise.query.count(),
        'Bài kiểm tra': Test.query.count(),
        'Khối đang theo dõi': len({student.grade_level for student in students if student.grade_level}),
    }
    recent_tests = Test.query.options(joinedload(Test.subject)).order_by(Test.id.desc()).limit(5).all()
    recent_lessons = Lesson.query.options(joinedload(Lesson.subject)).order_by(Lesson.id.desc()).limit(5).all()
    recent_exercises = Exercise.query.options(joinedload(Exercise.subject)).order_by(Exercise.id.desc()).limit(5).all()

    student_overview = []
    for student in students[:6]:
        submissions = Submission.query.filter_by(user_id=student.id).order_by(Submission.created_at.desc()).all()
        avg_score = round(sum((sub.score or 0) for sub in submissions) / len(submissions), 2) if submissions else 0
        student_overview.append({
            'student': student,
            'submission_count': len(submissions),
            'avg_score': avg_score,
            'latest_submission': submissions[0].created_at if submissions else None,
        })

    return render_template(
        'teacher/dashboard.html',
        stats=stats,
        recent_tests=recent_tests,
        recent_lessons=recent_lessons,
        recent_exercises=recent_exercises,
        student_overview=student_overview,
    )


@teacher_bp.route('/learning-results')
def learning_results():
    metrics = _teacher_learning_metrics()
    overview_stats = {
        'Tổng học viên': _student_query().count(),
        'Lượt nộp bài': sum(item['count'] for item in metrics['subject_submission_counts']),
        'Môn đang theo dõi': len(metrics['subject_submission_counts']),
        'Yêu cầu hỗ trợ': SupportRequest.query.filter_by(target_role='teacher').count(),
    }
    return render_template('teacher/learning_results.html', overview_stats=overview_stats, **metrics)

@teacher_bp.route('/students')
def students():
    selected_grade = request.args.get('grade_level', type=int)
    keyword = (request.args.get('keyword') or '').strip()

    query = _student_query()
    if selected_grade:
        query = query.filter(User.grade_level == selected_grade)
    if keyword:
        like_term = f'%{keyword}%'
        query = query.filter(
            or_(
                User.full_name.ilike(like_term),
                User.email.ilike(like_term),
                User.class_name.ilike(like_term),
            )
        )

    items = []
    for student in query.order_by(User.grade_level.asc(), User.class_name.asc(), User.full_name.asc()).all():
        submissions = Submission.query.filter_by(user_id=student.id).order_by(Submission.created_at.desc()).all()
        avg_score = round(sum((sub.score or 0) for sub in submissions) / len(submissions), 2) if submissions else 0
        support_total = SupportRequest.query.filter_by(user_id=student.id, target_role='teacher').count()
        items.append({
            'student': student,
            'submission_count': len(submissions),
            'avg_score': avg_score,
            'latest_submission': submissions[0].created_at if submissions else None,
            'support_total': support_total,
        })

    return render_template(
        'teacher/students.html',
        items=items,
        keyword=keyword,
        grade_level=selected_grade,
        grade_levels=list(range(6, 13)),
    )


@teacher_bp.route('/students/<int:item_id>/edit', methods=['GET', 'POST'])
def edit_student(item_id):
    item = User.query.filter_by(id=item_id, role='student').first_or_404()
    if request.method == 'POST':
        new_email = request.form.get('email', '').strip().lower()
        if not new_email or User.query.filter(User.email == new_email, User.id != item.id).first():
            flash('Email trống hoặc đã được tài khoản khác sử dụng.', 'danger')
            return render_template('teacher/student_form.html', student=item)
        item.full_name = request.form.get('full_name', '').strip()
        item.email = new_email
        item.grade_level = request.form.get('grade_level', type=int)
        item.class_name = request.form.get('class_name', '').strip()
        password = request.form.get('password', '').strip()
        if password:
            item.set_password(password)
        db.session.commit()
        flash('Đã cập nhật thông tin học viên.', 'success')
        return redirect(url_for('teacher.students'))
    return render_template('teacher/student_form.html', student=item)



@teacher_bp.route('/lessons')
def lessons():
    subject_id = request.args.get('subject_id', type=int)
    grade_level = request.args.get('grade_level', type=int)
    query = Lesson.query
    if subject_id:
        query = query.filter_by(subject_id=subject_id)
    if grade_level:
        query = query.filter_by(grade_level=grade_level)
    items = query.order_by(Lesson.grade_level.asc(), Lesson.chapter.asc()).all()
    return render_template('teacher/lessons.html', items=items, subjects=_subjects(), subject_id=subject_id, grade_level=grade_level, grade_levels=list(range(6, 13)))


@teacher_bp.route('/lessons/create', methods=['GET', 'POST'])
def create_lesson():
    if request.method == 'POST':
        item = Lesson(title=request.form.get('title', '').strip(), content=request.form.get('content', '').strip(), chapter=request.form.get('chapter', type=int), grade_level=request.form.get('grade_level', type=int), subject_id=request.form.get('subject_id', type=int))
        db.session.add(item)
        db.session.commit()
        flash('Đã thêm bài học.', 'success')
        return redirect(url_for('teacher.lessons'))
    return render_template('teacher/lesson_form.html', item=None, subjects=_subjects())


@teacher_bp.route('/lessons/<int:item_id>/edit', methods=['GET', 'POST'])
def edit_lesson(item_id):
    item = db.session.get(Lesson, item_id)
    if not item:
        abort(404)
    if request.method == 'POST':
        item.title = request.form.get('title', '').strip()
        item.content = request.form.get('content', '').strip()
        item.chapter = request.form.get('chapter', type=int)
        item.grade_level = request.form.get('grade_level', type=int)
        item.subject_id = request.form.get('subject_id', type=int)
        db.session.commit()
        flash('Đã cập nhật bài học.', 'success')
        return redirect(url_for('teacher.lessons'))
    preview_lines = [line.strip() for line in re.split(r'\n+|\.\s+', item.content or '') if line.strip()]
    return render_template('teacher/lesson_edit_view.html', item=item, subjects=_subjects(), preview_lines=preview_lines)


@teacher_bp.route('/lessons/<int:item_id>/delete', methods=['POST'])
def delete_lesson(item_id):
    item = db.session.get(Lesson, item_id)
    if not item:
        abort(404)
    db.session.delete(item)
    db.session.commit()
    flash('Đã xóa bài học.', 'info')
    return redirect(url_for('teacher.lessons'))


@teacher_bp.route('/exercises')
def exercises():
    subject_id = request.args.get('subject_id', type=int)
    grade_level = request.args.get('grade_level', type=int)
    query = Exercise.query
    if subject_id:
        query = query.filter_by(subject_id=subject_id)
    if grade_level:
        query = query.filter_by(grade_level=grade_level)
    items = query.order_by(Exercise.grade_level.asc(), Exercise.chapter.asc()).all()
    return render_template('teacher/exercises.html', items=items, subjects=_subjects(), subject_id=subject_id, grade_level=grade_level, grade_levels=list(range(6, 13)))


@teacher_bp.route('/exercises/create', methods=['GET', 'POST'])
def create_exercise():
    if request.method == 'POST':
        item = Exercise(title=request.form.get('title', '').strip(), content=request.form.get('content', '').strip(), answer_key=request.form.get('answer_key', '').strip(), chapter=request.form.get('chapter', type=int), grade_level=request.form.get('grade_level', type=int), subject_id=request.form.get('subject_id', type=int))
        db.session.add(item)
        db.session.commit()
        flash('Đã thêm bài tập.', 'success')
        return redirect(url_for('teacher.exercises'))
    return render_template('teacher/exercise_form.html', item=None, subjects=_subjects())


@teacher_bp.route('/exercises/<int:item_id>/edit', methods=['GET', 'POST'])
def edit_exercise(item_id):
    item = db.session.get(Exercise, item_id)
    if not item:
        abort(404)
    if request.method == 'POST':
        item.title = request.form.get('title', '').strip()
        item.content = request.form.get('content', '').strip()
        item.answer_key = request.form.get('answer_key', '').strip()
        item.chapter = request.form.get('chapter', type=int)
        item.grade_level = request.form.get('grade_level', type=int)
        item.subject_id = request.form.get('subject_id', type=int)
        questions = _extract_questions_from_form()
        if questions:
            item.set_question_bank(questions)
        db.session.commit()
        flash('Đã cập nhật bài tập.', 'success')
        return redirect(url_for('teacher.exercises'))
    questions = _exercise_editor_questions(item, commit_if_missing=True)
    return render_template('teacher/exercise_edit_view.html', item=item, subjects=_subjects(), questions=questions)


@teacher_bp.route('/exercises/<int:item_id>/delete', methods=['POST'])
def delete_exercise(item_id):
    item = db.session.get(Exercise, item_id)
    if not item:
        abort(404)
    db.session.delete(item)
    db.session.commit()
    flash('Đã xóa bài tập.', 'info')
    return redirect(url_for('teacher.exercises'))


@teacher_bp.route('/tests')
def tests():
    subject_id = request.args.get('subject_id', type=int)
    grade_level = request.args.get('grade_level', type=int)
    query = Test.query
    if subject_id:
        query = query.filter_by(subject_id=subject_id)
    if grade_level:
        query = query.filter_by(grade_level=grade_level)
    items = query.order_by(Test.grade_level.asc(), Test.test_type.asc(), Test.chapter.asc()).all()
    for item in items:
        item.display_type = _display_test_type(item)
    return render_template('teacher/tests.html', items=items, subjects=_subjects(), subject_id=subject_id, grade_level=grade_level, grade_levels=list(range(6, 13)))


@teacher_bp.route('/tests/create', methods=['GET', 'POST'])
def create_test():
    if request.method == 'POST':
        subject_id = request.form.get('subject_id', type=int)
        test_type = request.form.get('test_type', 'chapter').strip()
        chapter = request.form.get('chapter', type=int)
        subject = Subject.query.get_or_404(subject_id)
        title = request.form.get('title', '').strip() or _default_test_title(subject.name, test_type, chapter)
        if test_type != 'chapter':
            chapter = None
        item = Test(title=title, instructions=request.form.get('instructions', '').strip(), answer_key=request.form.get('answer_key', '').strip(), test_type=test_type, chapter=chapter, grade_level=request.form.get('grade_level', type=int), subject_id=subject_id)
        try:
            item.set_question_bank(generate_quick_quiz(subject.name, item.grade_level, chapter, count=30))
        except AIUnavailable:
            flash('AI đang bận nên chưa tạo được đề. Chưa lưu gì, hãy thử lại sau.', 'warning')
            return redirect(url_for('teacher.tests'))
        item.review_status = 'draft'
        db.session.add(item)
        db.session.commit()
        flash('Đã thêm bài kiểm tra.', 'success')
        return redirect(url_for('teacher.tests'))
    return render_template('teacher/test_form.html', item=None, subjects=_subjects())


@teacher_bp.route('/tests/ai-generate', methods=['GET', 'POST'])
def ai_generate_test():
    if request.method == 'POST':
        subject_id = request.form.get('subject_id', type=int)
        grade_level = request.form.get('grade_level', type=int)
        chapter = request.form.get('chapter', type=int)
        title = request.form.get('title', '').strip() or f'Đề AI - chương {chapter}'
        subject = Subject.query.get_or_404(subject_id)
        try:
            quiz = generate_quick_quiz(subject.name, grade_level, chapter, count=30)
        except AIUnavailable:
            flash('AI đang bận nên chưa tạo được đề. Chưa lưu gì, hãy thử lại sau.', 'warning')
            return redirect(url_for('teacher.ai_generate_test'))
        item = Test(title=title, instructions='Bài kiểm tra 30 câu trắc nghiệm, thời gian làm bài 60 phút, phân bổ độ khó dễ, trung bình, khó.' , answer_key='Đáp án nằm trong question_bank.', test_type='chapter', chapter=chapter, grade_level=grade_level, subject_id=subject_id)
        item.set_question_bank(quiz)
        db.session.add(item)
        db.session.commit()
        flash('Đã tạo đề nháp bằng AI. Hãy xem lại rồi bấm Duyệt để học sinh thấy đề.', 'success')
        return redirect(url_for('teacher.tests'))
    return render_template('teacher/ai_generate_test.html', subjects=_subjects())


@teacher_bp.route('/tests/<int:item_id>/edit', methods=['GET', 'POST'])
def edit_test(item_id):
    item = db.session.get(Test, item_id)
    if not item:
        abort(404)
    if request.method == 'POST':
        item.subject_id = request.form.get('subject_id', type=int)
        subject = Subject.query.get_or_404(item.subject_id)
        item.test_type = request.form.get('test_type', 'chapter').strip()
        item.chapter = request.form.get('chapter', type=int) if item.test_type == 'chapter' else None
        item.title = request.form.get('title', '').strip() or _default_test_title(subject.name, item.test_type, item.chapter)
        item.instructions = request.form.get('instructions', '').strip()
        item.answer_key = request.form.get('answer_key', '').strip()
        item.grade_level = request.form.get('grade_level', type=int)
        questions = _extract_questions_from_form()
        if questions:
            item.set_question_bank(questions)
        db.session.commit()
        flash('Đã cập nhật bài kiểm tra.', 'success')
        return redirect(url_for('teacher.tests'))
    questions = _test_editor_questions(item)
    return render_template('teacher/test_edit_view.html', item=item, subjects=_subjects(), questions=questions, display_type=_display_test_type(item))


@teacher_bp.route('/tests/<int:item_id>/approve', methods=['POST'])
def approve_test(item_id):
    item = db.session.get(Test, item_id)
    if not item:
        abort(404)
    item.review_status = 'approved' if request.form.get('action') != 'unapprove' else 'draft'
    db.session.commit()
    flash('Đã cập nhật trạng thái duyệt đề.', 'success')
    return redirect(url_for('teacher.tests'))


@teacher_bp.route('/tests/<int:item_id>/delete', methods=['POST'])
def delete_test(item_id):
    item = db.session.get(Test, item_id)
    if not item:
        abort(404)
    db.session.delete(item)
    db.session.commit()
    flash('Đã xóa bài kiểm tra.', 'info')
    return redirect(url_for('teacher.tests'))




@teacher_bp.route('/exercises/<int:item_id>/preview-answers')
def preview_exercise_answers(item_id):
    item = db.session.get(Exercise, item_id)
    if not item:
        abort(404)
    questions = _exercise_editor_questions(item, commit_if_missing=True)
    return _build_answer_preview_payload(
        questions=questions,
        label='Đáp án bài tập',
        title=item.title,
        back_url=url_for('teacher.exercises'),
        answer_note=item.answer_key or None,
        source_note='Bộ câu hỏi và đáp án này được đồng bộ theo đúng dữ liệu luyện tập của học sinh cho bài tập hiện tại.',
        summary={'subject': item.subject.name if item.subject else '-', 'grade_level': item.grade_level, 'chapter': item.chapter, 'total': len(questions)},
    )


@teacher_bp.route('/tests/<int:item_id>/preview-answers')
def preview_test_answers(item_id):
    item = db.session.get(Test, item_id)
    if not item:
        abort(404)
    questions = item.get_question_bank()
    return _build_answer_preview_payload(
        questions=questions,
        label='Đáp án bài kiểm tra',
        title=item.title,
        back_url=url_for('teacher.tests'),
        answer_note=item.answer_key or None,
        source_note='Đáp án lấy trực tiếp từ ngân hàng câu hỏi của bài kiểm tra đang hiển thị bên học sinh, gồm cả bài kiểm tra chương, giữa kì và cuối kì.',
        summary={'subject': item.subject.name if item.subject else '-', 'grade_level': item.grade_level, 'test_type': _display_test_type(item), 'total': len(questions)},
    )

@teacher_bp.route('/reports')
def reports():
    selected_grade = request.args.get('grade_level', type=int)
    selected_subject_id = request.args.get('subject_id', type=int)
    students = _student_query()
    if selected_grade:
        students = students.filter(User.grade_level == selected_grade)

    report_rows = []
    for student in students.order_by(User.grade_level.asc(), User.class_name.asc(), User.full_name.asc()).all():
        subs_query = Submission.query.filter_by(user_id=student.id)
        if selected_subject_id:
            subs_query = subs_query.outerjoin(Test, Submission.test_id == Test.id).outerjoin(Exercise, Submission.exercise_id == Exercise.id).filter(
                or_(Test.subject_id == selected_subject_id, Exercise.subject_id == selected_subject_id)
            )
        subs = subs_query.order_by(Submission.created_at.desc()).all()
        avg = round(sum((s.score or 0) for s in subs) / len(subs), 2) if subs else 0
        latest_submission = subs[0].created_at if subs else None
        report_rows.append({
            'student': student,
            'submission_count': len(subs),
            'avg_score': avg,
            'latest_submission': latest_submission,
        })

    return render_template(
        'teacher/reports.html',
        report_rows=report_rows,
        subjects=_subjects(),
        subject_id=selected_subject_id,
        grade_level=selected_grade,
        grade_levels=list(range(6, 13)),
    )


@teacher_bp.route('/support', methods=['GET', 'POST'])
def support():
    if request.method == 'POST':
        item_id = request.form.get('item_id', type=int)
        item = db.session.get(SupportRequest, item_id)
        if not item:
            abort(404)

        item.status = request.form.get('status', 'in_progress')
        item.response = request.form.get('response', '').strip()
        item.handled_by = current_user.id
        db.session.commit()
        flash('Đã cập nhật yêu cầu hỗ trợ.', 'success')
        return redirect(url_for('teacher.support', status=request.args.get('status', ''), keyword=request.args.get('keyword', '')))

    selected_status = (request.args.get('status') or '').strip()
    keyword = (request.args.get('keyword') or '').strip()

    items_query = SupportRequest.query.options(
        joinedload(SupportRequest.user),
        joinedload(SupportRequest.handler),
    ).filter(SupportRequest.target_role == 'teacher').order_by(SupportRequest.created_at.desc())

    if selected_status:
        items_query = items_query.filter(SupportRequest.status == selected_status)
    if keyword:
        like_term = f'%{keyword}%'
        items_query = items_query.join(User, SupportRequest.user_id == User.id).filter(
            or_(
                SupportRequest.title.ilike(like_term),
                SupportRequest.message.ilike(like_term),
                User.full_name.ilike(like_term),
                User.email.ilike(like_term),
            )
        )

    items = items_query.all()
    return render_template(
        'teacher/support.html',
        items=items,
        selected_status=selected_status,
        keyword=keyword,
        status_labels=SUPPORT_STATUS_LABELS,
    )


@teacher_bp.route('/support/reset-all', methods=['POST'])
def reset_all_support():
    items = SupportRequest.query.filter_by(target_role='teacher').all()
    for item in items:
        item.response = ''
        item.status = 'pending'
        item.handled_by = None
    db.session.commit()
    flash('Đã xóa toàn bộ phản hồi hỗ trợ của giáo viên và đưa về trạng thái ban đầu.', 'info')
    return redirect(url_for('teacher.support'))
