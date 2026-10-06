from datetime import datetime
import json

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from .extensions import db, login_manager


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    grade_level = db.Column(db.Integer)
    class_name = db.Column(db.String(30))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_teacher(self):
        return self.role in ["teacher", "admin"]

    @property
    def is_support(self):
        return self.role in ["support", "admin"]

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)


class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    chapter = db.Column(db.Integer, nullable=False)
    grade_level = db.Column(db.Integer, nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    subject = db.relationship("Subject")


class Exercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    answer_key = db.Column(db.Text, default="")
    question_bank = db.Column(db.Text, nullable=False, default="[]")
    chapter = db.Column(db.Integer, nullable=False)
    grade_level = db.Column(db.Integer, nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    subject = db.relationship("Subject")

    def get_question_bank(self):
        try:
            data = json.loads(self.question_bank or "[]")
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def set_question_bank(self, questions):
        self.question_bank = json.dumps(questions, ensure_ascii=False)


class Test(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    answer_key = db.Column(db.Text, default="")
    question_bank = db.Column(db.Text, nullable=False, default="[]")
    test_type = db.Column(db.String(20), nullable=False, default="chapter")
    review_status = db.Column(db.String(20), nullable=False, default="draft")  # draft | approved
    chapter = db.Column(db.Integer)
    grade_level = db.Column(db.Integer, nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subject.id"), nullable=False)
    subject = db.relationship("Subject")

    def get_question_bank(self):
        try:
            data = json.loads(self.question_bank or "[]")
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def set_question_bank(self, questions):
        self.question_bank = json.dumps(questions, ensure_ascii=False)


class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey("test.id"))
    exercise_id = db.Column(db.Integer, db.ForeignKey("exercise.id"))
    score = db.Column(db.Float, default=0)
    content = db.Column(db.Text, default="")
    feedback = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")
    test = db.relationship("Test")
    exercise = db.relationship("Exercise")


class SupportRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    handled_by = db.Column(db.Integer, db.ForeignKey("user.id"))

    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    target_role = db.Column(db.String(20), default="teacher")
    status = db.Column(db.String(30), default="pending")
    response = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", foreign_keys=[user_id])
    handler = db.relationship("User", foreign_keys=[handled_by])


class AIChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # user / assistant
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")


class QuizAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False)          # test | exercise | ai_quiz
    ref_id = db.Column(db.Integer, nullable=False)
    questions = db.Column(db.Text, nullable=False)           # JSON, CÓ đáp án, chỉ nằm ở server
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    deadline = db.Column(db.DateTime)
    submitted_at = db.Column(db.DateTime)

    def get_questions(self):
        return json.loads(self.questions)
