import json
import random
import re

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Subject, Lesson, Exercise, Test, Submission, SupportRequest, AIChatMessage
from ..services.ai_service import ask_ai
from ..services.ai_quiz import AIUnavailable, generate_quick_quiz, generate_exercise_quiz
from ..services.attempts import get_open_attempt, get_or_start_attempt, finish_attempt, minutes_left, grade_mcq
from ..services.subject_order import sort_subjects

student_bp = Blueprint('student', __name__, url_prefix='/student')


def _ensure_student():
    if current_user.role != 'student':
        abort(403)




def _matches_term_test(test, kind):
    title = (test.title or '').lower()
    test_type = (test.test_type or '').lower()
    mapping = {
        'midterm_hk1': ['midterm_hk1', 'giữa học kì 1', 'giữa học kỳ 1', 'giữa kì 1', 'giữa kỳ 1'],
        'midterm_hk2': ['midterm_hk2', 'giữa học kì 2', 'giữa học kỳ 2', 'giữa kì 2', 'giữa kỳ 2'],
        'final_hk1': ['final_hk1', 'cuối học kì 1', 'cuối học kỳ 1', 'cuối kì 1', 'cuối kỳ 1'],
        'final_hk2': ['final_hk2', 'cuối học kì 2', 'cuối học kỳ 2', 'cuối kì 2', 'cuối kỳ 2'],
    }
    keywords = mapping.get(kind, [])
    return any(key in title or key == test_type for key in keywords)

def _clean_chapter_topic(title, chapter=None):
    if not title:
        return ''

    cleaned = str(title).strip()

    # Xóa mọi tiền tố trước "Chương X", ví dụ:
    # "Toán 10 - Chương 1: Mệnh đề và tập hợp"
    # -> "Mệnh đề và tập hợp"
    if chapter:
        cleaned = re.sub(
            rf'^.*?chương\s*{chapter}\s*[:\-–.]?\s*',
            '',
            cleaned,
            flags=re.IGNORECASE
        ).strip()

    # Xóa các tiền tố kiểu "Bài học:", "Bài tập:", ...
    patterns = [
        r'^bài\s*học\s*[:\-–.]?\s*',
        r'^bài\s*tập\s*[:\-–.]?\s*',
        r'^bài\s*kiểm\s*tra\s*[:\-–.]?\s*',
        r'^kiểm\s*tra\s*[:\-–.]?\s*',
        r'^ôn\s*tập\s*[:\-–.]?\s*',
    ]

    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE).strip()

    cleaned = re.sub(r'^[:\-–.\s]+', '', cleaned).strip()
    return cleaned


def _chapter_topic_from_items(chapter, lesson=None, exercise=None, test=None):
    candidates = [
        lesson.title if lesson else '',
        exercise.title if exercise else '',
        test.title if test else '',
    ]
    for raw in candidates:
        cleaned = _clean_chapter_topic(raw, chapter)
        if cleaned and cleaned.lower() not in {'bài học', 'bài tập', 'bài kiểm tra'}:
            return cleaned
    return ''


def parse_plan(plan_text: str):
    if not plan_text:
        return []
    lines = [x.strip() for x in plan_text.splitlines() if x.strip()]
    days = []
    current_day = None
    current_section = None
    for line in lines:
        day_match = re.match(r'^Ngay\s*(\d+)\s*[:\-]\s*(.*)$', line, re.IGNORECASE)
        if not day_match:
            day_match = re.match(r'^Ngày\s*(\d+)\s*[:\-]\s*(.*)$', line, re.IGNORECASE)
        if day_match:
            if current_day:
                days.append(current_day)
            current_day = {
                'title': f'Ngày {day_match.group(1)}',
                'headline': day_match.group(2).strip(),
                'duration': '',
                'goal': '',
                'content_items': [],
                'exercise_items': [],
                'note_items': [],
            }
            current_section = None
            continue
        if current_day is None:
            continue
        lower_line = line.lower()
        if lower_line.startswith('thời lượng:') or lower_line.startswith('thoi luong:'):
            current_day['duration'] = line.split(':', 1)[1].strip()
            current_section = None
            continue
        if lower_line.startswith('mục tiêu:') or lower_line.startswith('muc tieu:'):
            current_day['goal'] = line.split(':', 1)[1].strip()
            current_section = None
            continue
        if lower_line.startswith('nội dung:') or lower_line.startswith('noi dung:'):
            current_section = 'content'
            continue
        if lower_line.startswith('bài tập:') or lower_line.startswith('bai tap:'):
            current_section = 'exercise'
            continue
        if lower_line.startswith('ghi chú:') or lower_line.startswith('ghi chu:'):
            current_section = 'note'
            continue
        if line.startswith('-'):
            item = line.lstrip('-').strip()
            if current_section == 'exercise':
                current_day['exercise_items'].append(item)
            elif current_section == 'note':
                current_day['note_items'].append(item)
            else:
                current_day['content_items'].append(item)
        else:
            if current_section == 'exercise':
                current_day['exercise_items'].append(line)
            elif current_section == 'note':
                current_day['note_items'].append(line)
            else:
                current_day['content_items'].append(line)
    if current_day:
        days.append(current_day)
    if not days:
        return [{
            'title': 'Lộ trình học',
            'headline': '',
            'duration': '',
            'goal': '',
            'content_items': [plan_text],
            'exercise_items': [],
            'note_items': [],
        }]
    return days


def _extract_focus_num(focus_chapter: str | None):
    if not focus_chapter:
        return None
    for token in str(focus_chapter).split():
        if token.isdigit():
            return int(token)
    match = re.search(r"(\d+)", str(focus_chapter))
    return int(match.group(1)) if match else None


def _build_local_plan(subject, lessons, exercises, tests, requested_days, daily_time, goal, focus_chapter, style, level, notes):
    chapter_pool = sorted({x.chapter for x in lessons if x.chapter} | {x.chapter for x in exercises if x.chapter} | {x.chapter for x in tests if x.chapter})
    if not chapter_pool:
        chapter_pool = list(range(1, min(requested_days, 4) + 1))

    lesson_by_ch = {x.chapter: x for x in lessons if x.chapter}
    exercise_by_ch = {x.chapter: x for x in exercises if x.chapter}
    chapter_test_by_ch = {x.chapter: x for x in tests if x.chapter and (x.test_type or '').lower() == 'chapter'}

    focus_num = _extract_focus_num(focus_chapter)
    ordered_chapters = []
    if focus_num and focus_num in chapter_pool:
        ordered_chapters.append(focus_num)
    ordered_chapters.extend([c for c in chapter_pool if c not in ordered_chapters])

    goal_lower = (goal or '').lower()
    wants_midterm = 'giữa' in goal_lower
    wants_final = 'cuối' in goal_lower
    midterm_test = next((x for x in tests if _matches_term_test(x, 'midterm_hk1') or _matches_term_test(x, 'midterm_hk2')), None)
    final_test = next((x for x in tests if _matches_term_test(x, 'final_hk1') or _matches_term_test(x, 'final_hk2')), None)

    style_note_map = {
        'Nhiều bài tập': 'Ưu tiên thời gian cho luyện đề, sau mỗi phần lý thuyết làm ngay câu hỏi vận dụng.',
        'Nhiều lý thuyết': 'Đọc kỹ khái niệm, công thức và ví dụ mẫu trước khi chuyển sang bài tập.',
        'Cân bằng lý thuyết và bài tập': 'Chia thời gian cân bằng: nửa đầu ôn kiến thức, nửa sau luyện tập.',
        'Ôn ngắn gọn, trọng tâm': 'Tập trung công thức trọng tâm, lỗi sai dễ gặp và 5-10 câu hỏi chọn lọc.',
    }
    level_note_map = {
        'Yếu': 'Ưu tiên câu cơ bản, làm chậm và ghi lại lỗi sai vào cuối buổi học.',
        'Trung bình': 'Cố gắng hoàn thành phần nhận biết và thông hiểu trước khi làm vận dụng.',
        'Khá': 'Thêm 2-3 câu vận dụng cuối buổi để nâng tốc độ và độ chính xác.',
        'Giỏi': 'Tăng câu hỏi phân hóa và tự giải thích lại lời giải bằng lời của mình.',
    }

    days = []
    for idx in range(requested_days):
        day_number = idx + 1
        chapter = ordered_chapters[idx % len(ordered_chapters)]
        lesson = lesson_by_ch.get(chapter)
        exercise = exercise_by_ch.get(chapter)
        chapter_test = chapter_test_by_ch.get(chapter)

        headline_target = focus_chapter if focus_num and idx < max(2, min(5, requested_days // 3 or 1)) else f'Chương {chapter}'
        content_items = []
        if lesson:
            content_items.append(f'Học bài trọng tâm: {lesson.title}')
        else:
            content_items.append(f'Ôn lý thuyết cốt lõi của Chương {chapter}')
        content_items.append(f'Tóm tắt khái niệm và công thức quan trọng của {headline_target}')
        if day_number % 3 == 0 and chapter_test:
            content_items.append(f'Rà soát nhanh bằng bài kiểm tra chương: {chapter_test.title}')

        exercise_items = []
        if exercise:
            exercise_items.append(f'Luyện bài tập: {exercise.title}')
        else:
            exercise_items.append(f'Làm 8-10 câu trắc nghiệm nhanh của Chương {chapter}')
        exercise_items.append('Tự kiểm tra lại các câu sai và ghi lại 3 ý cần nhớ sau buổi học')

        note_items = [
            f'Thời gian mỗi ngày: {daily_time}',
            style_note_map.get(style, 'Giữ nhịp học vừa sức, ưu tiên hiểu chắc trước khi làm nhanh.'),
            level_note_map.get(level, 'Theo dõi tiến độ và tự điều chỉnh độ khó phù hợp.'),
        ]
        if notes:
            note_items.append(f'Lưu ý riêng: {notes}')
        if focus_num and chapter == focus_num:
            note_items.append(f'Đây là chương trọng tâm cần ưu tiên: {focus_chapter}.')

        if wants_midterm and day_number in {max(2, requested_days // 2), requested_days}:
            exercise_items.append(f'Ôn theo đề giữa kì: {(midterm_test.title if midterm_test else "Làm 1 đề tổng hợp giữa kì 20-30 câu")}.')
        if wants_final and day_number in {max(3, requested_days - 2), requested_days}:
            exercise_items.append(f'Ôn theo đề cuối kì: {(final_test.title if final_test else "Làm 1 đề tổng hợp cuối kì 30-50 câu")}.')

        days.append({
            'title': f'Ngày {day_number}',
            'headline': f'{subject.name} - {headline_target}',
            'duration': daily_time,
            'goal': goal or f'Ôn chắc {headline_target}',
            'content_items': content_items,
            'exercise_items': exercise_items,
            'note_items': note_items,
        })

    return days


def _normalize_plan_days(parsed_days, fallback_days, requested_days, daily_time):
    plan_days = []
    for idx in range(requested_days):
        base = fallback_days[idx]
        raw = parsed_days[idx] if idx < len(parsed_days) else {}
        merged = {
            'title': f'Ngày {idx + 1}',
            'headline': (raw.get('headline') or base.get('headline') or '').strip(),
            'duration': (raw.get('duration') or base.get('duration') or daily_time or '').strip(),
            'goal': (raw.get('goal') or base.get('goal') or '').strip(),
            'content_items': raw.get('content_items') or base.get('content_items') or [],
            'exercise_items': raw.get('exercise_items') or base.get('exercise_items') or [],
            'note_items': raw.get('note_items') or base.get('note_items') or [],
        }
        plan_days.append(merged)
    return plan_days


@student_bp.before_request
@login_required
def before_student():
    _ensure_student()


@student_bp.route('/dashboard')
def dashboard():
    subjects = sort_subjects(Subject.query.all())
    recent_submissions = Submission.query.filter_by(user_id=current_user.id).order_by(Submission.created_at.desc()).limit(5).all()
    return render_template('student/dashboard.html', subjects=subjects, recent_submissions=recent_submissions)


@student_bp.route('/subject/<int:subject_id>')
def subject_detail(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    lessons = Lesson.query.filter_by(subject_id=subject_id, grade_level=current_user.grade_level).order_by(Lesson.chapter.asc()).all()
    exercises = Exercise.query.filter_by(subject_id=subject_id, grade_level=current_user.grade_level).order_by(Exercise.chapter.asc()).all()
    tests = Test.query.filter_by(subject_id=subject_id, grade_level=current_user.grade_level, review_status='approved').order_by(Test.chapter.asc().nullslast(), Test.title.asc()).all()
    lesson_by_ch = {x.chapter: x for x in lessons if x.chapter}
    exercise_by_ch = {x.chapter: x for x in exercises if x.chapter}
    test_by_ch = {x.chapter: x for x in tests if x.test_type == 'chapter' and x.chapter}

    available_chapters = sorted(set(
        [x.chapter for x in lessons if x.chapter] +
        [x.chapter for x in exercises if x.chapter] +
        [x.chapter for x in tests if x.chapter]
    ))

    blocks = []
    for chapter in available_chapters:
        lesson = lesson_by_ch.get(chapter)
        exercise = exercise_by_ch.get(chapter)
        test = test_by_ch.get(chapter)
        topic = _chapter_topic_from_items(chapter, lesson=lesson, exercise=exercise, test=test)
        heading = f'Chương {chapter} · {topic}' if topic else f'Chương {chapter}'
        blocks.append({'kind': 'chapter', 'chapter': chapter, 'heading': heading, 'topic': topic, 'lesson': lesson, 'exercise': exercise, 'test': test})
    term_map = [
        ('midterm_hk1', 'Kiểm tra giữa học kì 1'),
        ('midterm_hk2', 'Kiểm tra giữa học kì 2'),
        ('final_hk1', 'Kiểm tra cuối học kì 1'),
        ('final_hk2', 'Kiểm tra cuối học kì 2'),
    ]
    for kind, heading in term_map:
        term_test = next((x for x in tests if _matches_term_test(x, kind)), None)
        blocks.append({'kind': kind, 'chapter': None, 'heading': heading, 'lesson': None, 'exercise': None, 'test': term_test})
    return render_template('student/subject_detail.html', subject=subject, chapter_blocks=blocks)


@student_bp.route('/lesson/<int:item_id>')
def lesson_detail(item_id):
    lesson = Lesson.query.get_or_404(item_id)
    return render_template('student/lesson_detail.html', lesson=lesson)


@student_bp.route('/exercise/<int:item_id>', methods=['GET', 'POST'])
def exercise_detail(item_id):
    exercise = Exercise.query.get_or_404(item_id)
    if exercise.grade_level != current_user.grade_level:
        abort(404)
    if request.method == 'GET':
        try:
            att = get_or_start_attempt('exercise', item_id, lambda: _get_or_create_exercise_question_bank(exercise))
        except AIUnavailable:
            flash('AI đang bận nên chưa tạo được câu hỏi. Thử lại sau ít phút.', 'warning')
            return redirect(url_for('student.subject_detail', subject_id=exercise.subject_id))
        return render_template('student/exercise_detail.html', exercise=exercise, questions=att.get_questions())

    att = get_open_attempt('exercise', item_id)
    if not att:
        flash('Phiên làm bài tập đã hết. Hãy mở lại bài tập để làm tiếp.', 'warning')
        return redirect(url_for('student.exercise_detail', item_id=item_id))
    questions = att.get_questions()
    review_items, correct, answered_count, total, score = grade_mcq(questions, request.form)
    if not answered_count:
        flash('Bạn cần chọn tối thiểu 1 đáp án rồi mới nộp.', 'danger')
        return render_template('student/exercise_detail.html', exercise=exercise, questions=questions)
    wrong = [f"Câu {i['index']}" for i in review_items if i['selected'] and not i['is_correct']]
    feedback = f"Bạn làm đúng {correct}/{total} câu. " + (f"Cần xem lại: {', '.join(wrong[:5])}." if wrong else 'Tiếp tục luyện thêm để chắc hơn.')
    content = json.dumps({'mode': 'exercise', 'answered_count': answered_count, 'correct': correct,
                          'total': total, 'review_items': review_items}, ensure_ascii=False)
    sub = Submission(user_id=current_user.id, exercise_id=exercise.id, content=content, score=score, feedback=feedback)
    finish_attempt(att)
    db.session.add(sub)
    db.session.commit()
    flash(f'Đã nộp bài tập trắc nghiệm. Điểm của bạn: {score}/10', 'success')
    return redirect(url_for('student.submission_detail', submission_id=sub.id))


@student_bp.route('/test/<int:item_id>', methods=['GET', 'POST'])
def test_detail(item_id):
    test = Test.query.get_or_404(item_id)
    if test.grade_level != current_user.grade_level or test.review_status != 'approved':
        abort(404)
    if request.method == 'GET':
        bank = test.get_question_bank()
        if not bank:
            flash('Bài kiểm tra chưa có dữ liệu câu hỏi.', 'danger')
            return redirect(url_for('student.subject_detail', subject_id=test.subject_id))

        def make():
            pos = sorted(random.sample(range(len(bank)), min(30, len(bank))))   # random nhưng giữ thứ tự dễ -> khó
            return _prepare_question_payload([bank[i] for i in pos])

        att = get_or_start_attempt('test', item_id, make, minutes=60)
        qs = att.get_questions()
        return render_template('student/test_detail.html', test=test, questions=qs,
                               duration_minutes=minutes_left(att), total_questions=len(qs))

    att = get_open_attempt('test', item_id)
    if not att:
        flash('Phiên làm bài đã hết hạn hoặc đã nộp. Hãy mở lại bài kiểm tra.', 'warning')
        return redirect(url_for('student.subject_detail', subject_id=test.subject_id))
    review_items, correct, answered_count, total, score = grade_mcq(att.get_questions(), request.form)
    feedback = f'Bạn làm đúng {correct}/{total} câu. Đã trả lời {answered_count}/{total} câu.'
    content = json.dumps({'mode': 'test', 'answered_count': answered_count, 'correct': correct,
                          'total': total, 'review_items': review_items}, ensure_ascii=False)
    sub = Submission(user_id=current_user.id, test_id=test.id, score=score, content=content, feedback=feedback)
    finish_attempt(att)
    db.session.add(sub)
    db.session.commit()
    flash(f'Nộp bài thành công. Điểm của bạn: {score}', 'success')
    return redirect(url_for('student.submission_detail', submission_id=sub.id))


def _normalize_mcq_question(text: str) -> str:
    text = (text or '').strip()
    text = re.sub(r'^\s*Câu\s*\d+\s*[:.-]?\s*', '', text, flags=re.I)
    return text.strip()


def _difficulty_label(index: int, total: int) -> str:
    if total <= 0:
        return 'Trung bình'
    ratio = (index + 1) / total
    if ratio <= 0.3:
        return 'Dễ'
    if ratio <= 0.75:
        return 'Trung bình'
    return 'Khó'


def _prepare_question_payload(questions: list[dict], shuffle_questions: bool = False) -> list[dict]:
    prepared = []
    total = len(questions)
    for idx, q in enumerate(questions):
        item = dict(q)
        item['question'] = _normalize_mcq_question(item.get('question', ''))
        item['difficulty'] = item.get('difficulty') or _difficulty_label(idx, total)
        prepared.append(item)
    if shuffle_questions and len(prepared) > 1:
        random.shuffle(prepared)
    return prepared


def _get_or_create_exercise_question_bank(exercise: Exercise) -> list[dict]:
    stored_questions = exercise.get_question_bank() if hasattr(exercise, 'get_question_bank') else []
    if stored_questions:
        return _prepare_question_payload(stored_questions, shuffle_questions=False)

    generated = generate_exercise_quiz(
        exercise.subject.name if exercise.subject else 'môn học',
        exercise.title,
        exercise.content,
        current_user.grade_level,
        exercise.chapter,
        count=12,
    )
    prepared = _prepare_question_payload(generated, shuffle_questions=False)
    exercise.set_question_bank(prepared)      # chỉ tới được đây khi đề đã qua validate
    db.session.commit()
    return prepared


def _build_ai_quiz_context(subject, chapter: int):
    lesson = Lesson.query.filter_by(subject_id=subject.id, grade_level=current_user.grade_level, chapter=chapter).first()
    exercise = Exercise.query.filter_by(subject_id=subject.id, grade_level=current_user.grade_level, chapter=chapter).first()
    test = Test.query.filter_by(subject_id=subject.id, grade_level=current_user.grade_level, chapter=chapter, test_type='chapter').first()
    topic_hint = _chapter_topic_from_items(chapter, lesson=lesson, exercise=exercise, test=test) or f'Chương {chapter}'
    avoid_material = []
    if lesson and lesson.title:
        avoid_material.append(lesson.title)
    if exercise:
        avoid_material.extend([exercise.title or '', exercise.content or ''])
    if test:
        avoid_material.extend([test.title or '', test.instructions or ''])
    return topic_hint, [x for x in avoid_material if x]


@student_bp.route('/ai-quiz/<int:subject_id>/<int:chapter>', methods=['GET', 'POST'])
def ai_quiz_detail(subject_id, chapter):
    subject = Subject.query.get_or_404(subject_id)
    chapter = max(1, chapter or 1)
    topic_hint, avoid_material = _build_ai_quiz_context(subject, chapter)
    ref_id = subject_id * 1000 + chapter          # 1 lượt AI cho mỗi (môn, chương)

    if request.method == 'GET':
        def make():
            qs = generate_quick_quiz(subject.name, current_user.grade_level, chapter, topic_hint=topic_hint,
                                     count=20, avoid_material=avoid_material)
            return _prepare_question_payload(qs, shuffle_questions=True)
        try:
            att = get_or_start_attempt('ai_quiz', ref_id, make, minutes=25)
        except AIUnavailable:
            flash('AI đang bận nên chưa tạo được bộ đề. Thử lại sau ít phút.', 'warning')
            return redirect(url_for('student.subject_detail', subject_id=subject_id))
        quiz = {'title': f'Bộ đề AI · {subject.name} · Chương {chapter}',
                'instructions': f'20 câu trắc nghiệm về {topic_hint}.',
                'subject_name': subject.name, 'chapter': chapter, 'topic_hint': topic_hint}
        qs = att.get_questions()
        return render_template('student/ai_quiz_detail.html', quiz=quiz, questions=qs,
                               duration_minutes=minutes_left(att, 25), total_questions=len(qs), subject=subject)

    att = get_open_attempt('ai_quiz', ref_id)
    if not att:
        flash('Phiên đề AI đã hết hạn hoặc đã nộp. Hãy tạo lại bộ đề mới.', 'warning')
        return redirect(url_for('student.subject_detail', subject_id=subject_id))
    review_items, correct, answered_count, total, score = grade_mcq(att.get_questions(), request.form)
    finish_attempt(att)
    db.session.commit()
    return render_template('student/ai_quiz_result.html', subject=subject, chapter=chapter, topic_hint=topic_hint,
                           score=score, correct=correct, total=total, answered_count=answered_count, review_items=review_items)


def _parse_submission_review(submission: Submission):
    try:
        payload = json.loads(submission.content or '{}')
        if isinstance(payload, dict) and isinstance(payload.get('review_items'), list):
            return payload
    except Exception:
        pass
    return None


@student_bp.route('/submission/<int:submission_id>')
def submission_detail(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    if submission.user_id != current_user.id:
        abort(403)

    payload = _parse_submission_review(submission)
    if not payload:
        flash('Bài làm này chưa có dữ liệu xem lại chi tiết.', 'warning')
        return redirect(url_for('student.results'))

    item = submission.exercise or submission.test
    item_type = 'Bài tập' if submission.exercise_id else 'Bài kiểm tra'
    return render_template(
        'student/submission_review.html',
        submission=submission,
        item=item,
        item_type=item_type,
        score=submission.score or 0,
        correct=payload.get('correct', 0),
        total=payload.get('total', 0),
        answered_count=payload.get('answered_count', 0),
        review_items=payload.get('review_items', []),
    )


@student_bp.route('/results')
def results():
    items = Submission.query.filter_by(user_id=current_user.id).order_by(Submission.created_at.desc()).all()
    return render_template('student/results.html', items=items)


@student_bp.route('/plan-builder', methods=['GET', 'POST'])
def plan_builder():
    subjects = sort_subjects(Subject.query.all())
    if request.method == 'POST':
        subject_id = request.form.get('subject_id', type=int)
        subject = Subject.query.get_or_404(subject_id)
        goal = request.form.get('goal', '').strip()
        requested_days = request.form.get('plan_days', type=int) or 7
        if requested_days not in {7, 14, 30}:
            requested_days = 7
        daily_time = request.form.get('daily_time', '').strip()
        focus_chapter = request.form.get('focus_chapter', '').strip()
        style = request.form.get('style', '').strip()
        level = request.form.get('level', '').strip()
        notes = request.form.get('notes', '').strip()

        lessons = Lesson.query.filter_by(subject_id=subject.id, grade_level=current_user.grade_level).order_by(Lesson.chapter.asc()).all()
        exercises = Exercise.query.filter_by(subject_id=subject.id, grade_level=current_user.grade_level).order_by(Exercise.chapter.asc()).all()
        tests = Test.query.filter_by(subject_id=subject.id, grade_level=current_user.grade_level).order_by(Test.test_type.asc(), Test.chapter.asc()).all()

        plan_prompt = f"""
Hãy tạo lộ trình học {requested_days} ngày cho học sinh lớp {current_user.grade_level}.

Thông tin:
- Môn học: {subject.name}
- Mục tiêu: {goal}
- Chương đang yếu: {focus_chapter}
- Mức độ hiện tại: {level}
- Phong cách học mong muốn: {style}
- Thời gian học mỗi ngày: {daily_time}
- Ghi chú thêm: {notes if notes else 'Không có'}

YÊU CẦU RẤT QUAN TRỌNG:
- BẮT BUỘC tạo đúng {requested_days} ngày, không thiếu ngày nào.
- Mỗi ngày chỉ ghi đúng theo format bên dưới.
- Không viết mở đầu, không viết kết luận chung, không viết markdown.
- Nội dung phải ngắn gọn, dễ đọc, bám sát chương và mục tiêu.

Lặp lại khối mẫu này cho đủ từ Ngày 1 đến hết Ngày {requested_days}:
Ngày X: [tiêu đề ngắn]
Thời lượng: {daily_time}
Mục tiêu: ...
Nội dung:
- ...
- ...
- ...
Bài tập:
- ...
- ...
Ghi chú:
- ...
- ...
""".strip()

        plan_text = ask_ai(plan_prompt, current_user.grade_level)
        parsed_days = parse_plan(plan_text)
        fallback_days = _build_local_plan(subject, lessons, exercises, tests, requested_days, daily_time, goal, focus_chapter, style, level, notes)

        error_signals = ['Lỗi khi gọi Gemini API', 'Gemini không trả về nội dung', 'Chưa cấu hình Gemini API key']
        if (not parsed_days or len(parsed_days) != requested_days or any(signal in plan_text for signal in error_signals)):
            plan_days = fallback_days
        else:
            plan_days = _normalize_plan_days(parsed_days, fallback_days, requested_days, daily_time)

        focus_num = _extract_focus_num(focus_chapter)

        customized_items = []
        if focus_num:
            for lesson in lessons:
                if lesson.chapter == focus_num:
                    customized_items.append({'label': 'Bài học trọng tâm', 'title': lesson.title, 'url': url_for('student.lesson_detail', item_id=lesson.id)})
            for exercise in exercises:
                if exercise.chapter == focus_num:
                    customized_items.append({'label': 'Bài tập trọng tâm', 'title': exercise.title, 'url': url_for('student.exercise_detail', item_id=exercise.id)})
            for test in tests:
                if test.chapter == focus_num and test.test_type == 'chapter':
                    customized_items.append({'label': 'Kiểm tra trọng tâm', 'title': test.title, 'url': url_for('student.test_detail', item_id=test.id)})

        if not customized_items:
            for lesson in lessons[:2]:
                customized_items.append({'label': 'Bài học gợi ý', 'title': lesson.title, 'url': url_for('student.lesson_detail', item_id=lesson.id)})
            for exercise in exercises[:2]:
                customized_items.append({'label': 'Bài tập gợi ý', 'title': exercise.title, 'url': url_for('student.exercise_detail', item_id=exercise.id)})
            for test in tests[:1]:
                customized_items.append({'label': 'Kiểm tra gợi ý', 'title': test.title, 'url': url_for('student.test_detail', item_id=test.id)})

        plan_input = {'subject': subject.name, 'goal': goal, 'plan_days': requested_days, 'daily_time': daily_time, 'focus_chapter': focus_chapter, 'style': style, 'level': level, 'notes': notes}
        return render_template('student/plan_view.html', subject=subject, plan_days=plan_days, customized_items=customized_items, plan_input=plan_input)

    chapter_options = list(range(1, 11))
    plan_day_presets = [(7, '1 tuần'), (14, '2 tuần'), (30, '1 tháng')]
    plan_suggestions = [
        {
            'title': 'Ôn tăng tốc 1 tuần',
            'subtitle': 'Phù hợp khi sắp kiểm tra và cần bám chương yếu nhất.',
            'days': 7,
            'goal': 'Tăng điểm nhanh',
            'style': 'Ôn ngắn gọn, trọng tâm',
            'daily_time': '60 phút',
            'level': 'Trung bình',
            'notes': 'Ưu tiên câu dễ ăn điểm và rà lỗi sai cuối mỗi buổi.'
        },
        {
            'title': 'Củng cố đều trong 2 tuần',
            'subtitle': 'Hợp khi muốn học chắc hơn và chia đều lý thuyết với bài tập.',
            'days': 14,
            'goal': 'Củng cố kiến thức',
            'style': 'Cân bằng lý thuyết và bài tập',
            'daily_time': '60 phút',
            'level': 'Trung bình',
            'notes': 'Mỗi 3 ngày tự kiểm tra nhanh 1 lần để theo dõi tiến bộ.'
        },
        {
            'title': 'Học chắc 1 tháng',
            'subtitle': 'Dành cho khi cần lấy lại nền tảng từ gốc đến chắc.',
            'days': 30,
            'goal': 'Học chắc từ gốc',
            'style': 'Nhiều lý thuyết',
            'daily_time': '45 phút',
            'level': 'Yếu',
            'notes': 'Đi chậm nhưng chắc, ghi lại công thức và ví dụ mẫu sau mỗi buổi.'
        },
    ]
    return render_template('student/plan_builder.html', subjects=subjects, chapter_options=chapter_options, plan_day_presets=plan_day_presets, plan_suggestions=plan_suggestions)


@student_bp.route('/ai', methods=['GET', 'POST'])
def ai_center():
    subjects = sort_subjects(Subject.query.all())
    selected_subject_id = request.args.get('subject_id', type=int) or (subjects[0].id if subjects else None)
    selected_chapter = request.args.get('chapter', type=int) or 1
    chats = AIChatMessage.query.filter_by(user_id=current_user.id).order_by(AIChatMessage.created_at.asc()).all()

    if request.method == 'POST':
        action = request.form.get('action', '').strip()
        if action == 'chat':
            user_message = request.form.get('message', '').strip()
            subject_id = request.form.get('subject_id', type=int)
            chapter = request.form.get('chapter', type=int)
            mode = request.form.get('mode', 'explain').strip()
            subject = Subject.query.get(subject_id) if subject_id else None
            subject_name = subject.name if subject else 'môn học bất kỳ'
            if user_message:
                if mode == 'explain':
                    final_prompt = f"""
Em là học sinh lớp {current_user.grade_level}.
Hãy giải thích dễ hiểu, chia ý rõ ràng, ngắn gọn, dùng ngôn ngữ gần gũi như gia sư.
Môn: {subject_name}
Chương: {chapter}
Câu hỏi: {user_message}
""".strip()
                elif mode == 'solve':
                    final_prompt = f"""
Em là học sinh lớp {current_user.grade_level}.
Hãy giải bài này từng bước thật rõ.
Cấu trúc:
1. Phân tích đề
2. Cách làm
3. Lời giải chi tiết
4. Kết luận
Môn: {subject_name}
Chương: {chapter}
Đề bài: {user_message}
""".strip()
                elif mode == 'quiz':
                    final_prompt = f"""
Tạo 3 câu hỏi trắc nghiệm ngắn để học sinh lớp {current_user.grade_level} tự luyện.
Môn: {subject_name}
Chương: {chapter}
Chủ đề: {user_message}

Format:
Câu 1: ...
A. ...
B. ...
C. ...
D. ...
Đáp án: ...

Câu 2: ...
...

Câu 3: ...
...
""".strip()
                else:
                    final_prompt = f"""
Em là học sinh lớp {current_user.grade_level}.
Môn: {subject_name}
Chương: {chapter}
Yêu cầu: {user_message}
""".strip()
                db.session.add(AIChatMessage(user_id=current_user.id, role='user', message=f'[{subject_name} - Chương {chapter}] {user_message}'))
                answer = ask_ai(final_prompt, current_user.grade_level)
                db.session.add(AIChatMessage(user_id=current_user.id, role='assistant', message=answer))
                db.session.commit()
                return redirect(url_for('student.ai_center', subject_id=subject_id, chapter=chapter))
    return render_template('student/ai_center.html', subjects=subjects, chats=chats, selected_subject_id=selected_subject_id, selected_chapter=selected_chapter)


@student_bp.route('/ai/clear', methods=['POST'])
def clear_ai_chat():
    AIChatMessage.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash('Đã xóa lịch sử chat AI.', 'info')
    return redirect(url_for('student.ai_center'))


@student_bp.route('/support/clear', methods=['POST'])
def clear_support_history():
    SupportRequest.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash('Đã xóa lịch sử yêu cầu hỗ trợ.', 'info')
    return redirect(url_for('student.support'))


@student_bp.route('/support', methods=['GET', 'POST'])
def support():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        message = request.form.get('message', '').strip()
        target_role = request.form.get('target_role', 'teacher').strip()
        if target_role not in ['teacher', 'admin']:
            target_role = 'teacher'
        if title and message:
            item = SupportRequest(user_id=current_user.id, title=title, message=message, target_role=target_role)
            db.session.add(item)
            db.session.commit()
            flash('Đã gửi yêu cầu hỗ trợ.', 'success')
            return redirect(url_for('student.support'))
        flash('Vui lòng nhập đủ tiêu đề và nội dung.', 'danger')

    items = SupportRequest.query.filter_by(user_id=current_user.id).order_by(SupportRequest.created_at.desc()).all()
    return render_template('student/support.html', items=items)
