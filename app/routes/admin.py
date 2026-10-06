from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import User, Subject, Lesson, Exercise, Test, SupportRequest, Submission, AIChatMessage, QuizAttempt
from ..services.subject_order import sort_subjects

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

SUPPORT_STATUS_LABELS = {
    'pending': 'Chờ xử lý',
    'in_progress': 'Đang xử lý',
    'done': 'Đã hoàn thành',
}

SUPPORT_TARGET_LABELS = {
    'teacher': 'Gửi cho giáo viên',
    'admin': 'Gửi cho admin hệ thống',
}


def _ensure_admin():
    if not current_user.is_authenticated:
        abort(401)
    if getattr(current_user, 'role', None) != 'admin':
        abort(403)


def _account_query():
    return User.query.order_by(User.role.asc(), User.full_name.asc())


def _subjects():
    return sort_subjects(Subject.query.all())


@admin_bp.before_request
@login_required
def check_admin_role():
    _ensure_admin()


@admin_bp.route('/dashboard')
def dashboard():
    stats = {
        'Tổng tài khoản': User.query.count(),
        'Học viên': User.query.filter_by(role='student').count(),
        'Giáo viên': User.query.filter_by(role='teacher').count(),
        'Admin': User.query.filter_by(role='admin').count(),
        'Môn học': Subject.query.count(),
        'Yêu cầu gửi admin': SupportRequest.query.filter_by(target_role='admin').count(),
    }
    recent_accounts = _account_query().limit(8).all()
    pending_support = SupportRequest.query.filter(
        SupportRequest.target_role == 'admin',
        SupportRequest.status != 'done'
    ).order_by(SupportRequest.created_at.desc()).limit(5).all()
    content_stats = {
        'Bài học': Lesson.query.count(),
        'Bài tập': Exercise.query.count(),
        'Bài kiểm tra': Test.query.count(),
    }
    return render_template(
        'admin/dashboard.html',
        stats=stats,
        recent_accounts=recent_accounts,
        pending_support=pending_support,
        content_stats=content_stats,
        status_labels=SUPPORT_STATUS_LABELS,
        target_labels=SUPPORT_TARGET_LABELS,
    )


@admin_bp.route('/accounts')
def accounts():
    return render_template('admin/accounts.html', accounts=_account_query().all())


@admin_bp.route('/system')
def system():
    system_stats = {
        'Người dùng': User.query.count(),
        'Tin nhắn AI': AIChatMessage.query.count(),
        'Yêu cầu hỗ trợ': SupportRequest.query.count(),
        'Lượt nộp bài': Submission.query.count(),
        'Môn học': Subject.query.count(),
    }
    return render_template('admin/system.html', system_stats=system_stats)


@admin_bp.route('/system/clear-ai-chat', methods=['POST'])
def clear_all_ai_chat():
    total = AIChatMessage.query.delete()
    db.session.commit()
    flash(f'Đã xóa {total} tin nhắn trong lịch sử chat AI toàn hệ thống.', 'info')
    return redirect(url_for('admin.system'))


@admin_bp.route('/system/clear-support', methods=['POST'])
def clear_all_support_requests():
    total = SupportRequest.query.delete()
    db.session.commit()
    flash(f'Đã xóa {total} yêu cầu hỗ trợ/lịch sử yêu cầu.', 'info')
    return redirect(url_for('admin.system'))


@admin_bp.route('/system/clear-submissions', methods=['POST'])
def clear_all_submissions():
    total = Submission.query.delete()
    db.session.commit()
    flash(f'Đã xóa {total} lượt nộp bài và kết quả liên quan.', 'info')
    return redirect(url_for('admin.system'))


@admin_bp.route('/accounts/create', methods=['GET', 'POST'])
def create_account():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'student').strip()
        grade_level = request.form.get('grade_level', type=int)
        class_name = request.form.get('class_name', '').strip()
        if not full_name or not email:
            flash('Vui lòng nhập đầy đủ họ tên và email.', 'danger')
            return render_template('admin/account_form.html', account=None)
        if len(password) < 6:
            flash('Mật khẩu phải có ít nhất 6 ký tự.', 'danger')
            return render_template('admin/account_form.html', account=None)
        if User.query.filter_by(email=email).first():
            flash('Email đã tồn tại.', 'danger')
            return render_template('admin/account_form.html', account=None)
        account = User(full_name=full_name, email=email, role=role)
        if role == 'student':
            account.grade_level = grade_level
            account.class_name = class_name
        account.set_password(password)
        db.session.add(account)
        db.session.commit()
        flash('Đã tạo tài khoản mới.', 'success')
        return redirect(url_for('admin.accounts'))
    return render_template('admin/account_form.html', account=None)


@admin_bp.route('/accounts/<int:item_id>/edit', methods=['GET', 'POST'])
def edit_account(item_id):
    account = db.session.get(User, item_id)
    if not account:
        abort(404)
    if request.method == 'POST':
        new_email = request.form.get('email', '').strip().lower()
        existed = User.query.filter(User.email == new_email, User.id != account.id).first()
        if existed:
            flash('Email đã tồn tại.', 'danger')
            return render_template('admin/account_form.html', account=account)
        role = request.form.get('role', account.role).strip()
        account.full_name = request.form.get('full_name', '').strip()
        account.email = new_email
        account.role = role
        if role == 'student':
            account.grade_level = request.form.get('grade_level', type=int)
            account.class_name = request.form.get('class_name', '').strip()
        else:
            account.grade_level = None
            account.class_name = None
        new_password = request.form.get('password', '').strip()
        if new_password:
            account.set_password(new_password)
        db.session.commit()
        flash('Đã cập nhật tài khoản.', 'success')
        return redirect(url_for('admin.accounts'))
    return render_template('admin/account_form.html', account=account)


@admin_bp.route('/accounts/<int:item_id>/delete', methods=['POST'])
def delete_account(item_id):
    account = db.session.get(User, item_id)
    if not account:
        abort(404)
    if account.id == current_user.id:
        flash('Không thể xóa chính tài khoản admin đang đăng nhập.', 'danger')
        return redirect(url_for('admin.accounts'))
    # SQLite không tự cascade: dọn dữ liệu của tài khoản để không còn bản ghi mồ côi
    Submission.query.filter_by(user_id=account.id).delete()
    AIChatMessage.query.filter_by(user_id=account.id).delete()
    QuizAttempt.query.filter_by(user_id=account.id).delete()
    SupportRequest.query.filter_by(user_id=account.id).delete()
    SupportRequest.query.filter_by(handled_by=account.id).update({'handled_by': None})
    db.session.delete(account)
    db.session.commit()
    flash('Đã xóa tài khoản.', 'info')
    return redirect(url_for('admin.accounts'))


@admin_bp.route('/subjects')
def subjects():
    return render_template('admin/subjects.html', subjects=_subjects())


@admin_bp.route('/subjects/create', methods=['POST'])
def create_subject():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Vui lòng nhập tên môn học.', 'danger')
    elif Subject.query.filter_by(name=name).first():
        flash('Môn học đã tồn tại.', 'danger')
    else:
        db.session.add(Subject(name=name))
        db.session.commit()
        flash('Đã thêm môn học.', 'success')
    return redirect(url_for('admin.subjects'))


@admin_bp.route('/subjects/<int:item_id>/edit', methods=['POST'])
def edit_subject(item_id):
    item = db.session.get(Subject, item_id)
    if not item:
        abort(404)
    name = request.form.get('name', '').strip()
    if not name:
        flash('Tên môn học không được để trống.', 'danger')
    else:
        item.name = name
        db.session.commit()
        flash('Đã cập nhật môn học.', 'success')
    return redirect(url_for('admin.subjects'))


@admin_bp.route('/subjects/<int:item_id>/delete', methods=['POST'])
def delete_subject(item_id):
    item = db.session.get(Subject, item_id)
    if not item:
        abort(404)
    if Lesson.query.filter_by(subject_id=item.id).first() or Exercise.query.filter_by(subject_id=item.id).first() or Test.query.filter_by(subject_id=item.id).first():
        flash('Môn học còn bài học / bài tập / bài kiểm tra nên không thể xóa. Hãy xóa nội dung trước.', 'danger')
        return redirect(url_for('admin.subjects'))
    db.session.delete(item)
    db.session.commit()
    flash('Đã xóa môn học.', 'info')
    return redirect(url_for('admin.subjects'))


@admin_bp.route('/support', methods=['GET', 'POST'])
def support():
    if request.method == 'POST':
        item_id = request.form.get('item_id', type=int)
        item = db.session.get(SupportRequest, item_id)
        if not item:
            abort(404)
        item.status = request.form.get('status', 'in_progress')
        item.response = request.form.get('response', '').strip()
        item.handled_by = current_user.id if item.response else None
        db.session.commit()
        flash('Đã cập nhật phản hồi hỗ trợ.', 'success')
        return redirect(url_for('admin.support', status=request.args.get('status', ''), keyword=request.args.get('keyword', '')))

    selected_status = (request.args.get('status') or '').strip()
    keyword = (request.args.get('keyword') or '').strip()

    items_query = SupportRequest.query.options(
        joinedload(SupportRequest.user),
        joinedload(SupportRequest.handler),
    ).filter(SupportRequest.target_role == 'admin').order_by(SupportRequest.created_at.desc())

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
        'admin/support.html',
        items=items,
        selected_status=selected_status,
        keyword=keyword,
        status_labels=SUPPORT_STATUS_LABELS,
        target_labels=SUPPORT_TARGET_LABELS,
    )


@admin_bp.route('/support/reset-all', methods=['POST'])
def reset_all_support():
    items = SupportRequest.query.filter_by(target_role='admin').all()
    for item in items:
        item.response = ''
        item.status = 'pending'
        item.handled_by = None
    db.session.commit()
    flash('Đã xóa toàn bộ phản hồi hỗ trợ của admin và đưa về trạng thái ban đầu.', 'info')
    return redirect(url_for('admin.support'))
