from flask import Blueprint, render_template
from flask_login import current_user

main_bp = Blueprint('main', __name__)


def _target_url():
    if current_user.role == 'admin':
        return '/admin/dashboard'
    if current_user.role == 'teacher':
        return '/teacher/dashboard'
    return '/student/dashboard'


@main_bp.route('/')
def home():
    if current_user.is_authenticated:
        return render_template('redirect_dashboard.html', target_url=_target_url())
    return render_template('home.html')


@main_bp.route('/dashboard')
def dashboard_redirect():
    if current_user.is_authenticated:
        return render_template('redirect_dashboard.html', target_url=_target_url())
    return render_template('home.html')
