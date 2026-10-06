import os
from pathlib import Path
from flask import Flask, flash, redirect, url_for
from dotenv import load_dotenv
from sqlalchemy import text

from flask_wtf.csrf import CSRFProtect, CSRFError
from .extensions import db, login_manager

csrf = CSRFProtect()
from .seed import seed_data


def ensure_database_updates():
    support_columns = db.session.execute(text("PRAGMA table_info(support_request)")).fetchall()
    support_column_names = [col[1] for col in support_columns]
    if 'target_role' not in support_column_names:
        db.session.execute(text("ALTER TABLE support_request ADD COLUMN target_role VARCHAR(20) DEFAULT 'teacher'"))
        db.session.commit()
    db.session.execute(text("UPDATE support_request SET target_role = 'teacher' WHERE target_role IS NULL OR target_role = ''"))
    db.session.commit()

    exercise_columns = db.session.execute(text("PRAGMA table_info(exercise)")).fetchall()
    exercise_column_names = [col[1] for col in exercise_columns]
    if 'question_bank' not in exercise_column_names:
        db.session.execute(text("ALTER TABLE exercise ADD COLUMN question_bank TEXT DEFAULT '[]'"))
        db.session.commit()
    db.session.execute(text("UPDATE exercise SET question_bank = '[]' WHERE question_bank IS NULL OR question_bank = ''"))
    db.session.commit()


def ensure_review_status():
    cols = [c[1] for c in db.session.execute(text("PRAGMA table_info(test)")).fetchall()]
    if 'review_status' not in cols:
        # đề cũ là câu mẫu sinh bằng template -> coi như chưa đạt, chờ build lại
        db.session.execute(text("ALTER TABLE test ADD COLUMN review_status VARCHAR(20) NOT NULL DEFAULT 'draft'"))
        db.session.commit()


def create_app():
    base_dir = Path(__file__).resolve().parent.parent
    env_path = base_dir / ".env"
    load_dotenv(env_path)

    print("ENV PATH:", env_path)
    print("GEMINI_API_KEY loaded:", bool(os.environ.get("GEMINI_API_KEY")))

    app = Flask(__name__)
    secret = os.environ.get("SECRET_KEY", "").strip()
    if len(secret) < 32 or secret in ("change-me", "dev-secret-key"):
        raise RuntimeError(
            "Thiếu SECRET_KEY hợp lệ trong file .env (cần >= 32 ký tự ngẫu nhiên). "
            'Tạo bằng: python -c "import secrets; print(secrets.token_hex(32))"'
        )
    app.config["SECRET_KEY"] = secret
    app.config["WTF_CSRF_TIME_LIMIT"] = None
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///study_platform.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    csrf.init_app(app)
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    from .routes.main import main_bp
    from .routes.auth import auth_bp
    from .routes.admin import admin_bp
    from .routes.teacher import teacher_bp
    from .routes.student import student_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(student_bp)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(_err):
        flash("Phiên làm việc đã hết hạn hoặc yêu cầu không hợp lệ. Hãy tải lại trang rồi thử lại.", "danger")
        return redirect(url_for("main.home"))

    with app.app_context():
        db.create_all()
        ensure_database_updates()
        ensure_review_status()
        seed_data()

    return app
