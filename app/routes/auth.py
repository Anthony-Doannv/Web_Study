from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from ..extensions import db
from ..models import User

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard_redirect'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'student').strip()
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash('Sai email hoặc mật khẩu.', 'danger')
            return render_template('auth/login.html')
        if user.role != role:
            flash('Vai trò đăng nhập không đúng với tài khoản này.', 'danger')
            return render_template('auth/login.html')
        login_user(user)
        flash('Đăng nhập thành công.', 'success')
        if user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        if user.role == 'teacher':
            return redirect(url_for('teacher.dashboard'))
        return redirect(url_for('student.dashboard'))
    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        role = 'student'
        grade_level = request.form.get('grade_level', type=int)
        class_name = request.form.get('class_name', '').strip()
        if not full_name or not email or not password:
            flash('Vui lòng nhập đầy đủ thông tin.', 'danger')
            return render_template('auth/register.html')
        if len(password) < 6:
            flash('Mật khẩu phải có ít nhất 6 ký tự.', 'danger')
            return render_template('auth/register.html')
        if grade_level is None or not class_name:
            flash('Vui lòng nhập đầy đủ khối và lớp cho tài khoản học sinh.', 'danger')
            return render_template('auth/register.html')
        existed = User.query.filter_by(email=email).first()
        if existed:
            flash('Email đã tồn tại.', 'danger')
            return render_template('auth/register.html')
        user = User(full_name=full_name, email=email, role=role, grade_level=grade_level, class_name=class_name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Đăng ký thành công. Hãy đăng nhập.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html')


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('Đã đăng xuất thành công.', 'success')
    return redirect(url_for('auth.login'))
