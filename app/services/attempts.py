"""Lưu đề đang làm ở SERVER (bảng quiz_attempt). Cookie chỉ giữ id của lượt làm bài."""
import json
import math
from datetime import datetime, timedelta

from flask import session
from flask_login import current_user

from ..extensions import db
from ..models import QuizAttempt

LETTERS = {"A", "B", "C", "D"}
GRACE = timedelta(minutes=2)          # du di mạng khi nộp sát giờ


def _key(kind, ref_id):
    return f"attempt_{kind}_{ref_id}"


def get_open_attempt(kind, ref_id):
    """Trả về lượt làm bài còn hiệu lực của user hiện tại, hoặc None."""
    att_id = session.get(_key(kind, ref_id))
    att = db.session.get(QuizAttempt, att_id) if att_id else None
    if not att or att.user_id != current_user.id or att.submitted_at:
        return None
    if att.deadline and datetime.utcnow() > att.deadline + GRACE:
        return None
    return att


def start_attempt(kind, ref_id, questions, minutes=None):
    QuizAttempt.query.filter_by(user_id=current_user.id, kind=kind,
                                ref_id=ref_id, submitted_at=None).delete()
    att = QuizAttempt(
        user_id=current_user.id, kind=kind, ref_id=ref_id,
        questions=json.dumps(questions, ensure_ascii=False),
        deadline=datetime.utcnow() + timedelta(minutes=minutes) if minutes else None,
    )
    db.session.add(att)
    db.session.commit()
    session[_key(kind, ref_id)] = att.id
    return att


def get_or_start_attempt(kind, ref_id, make_questions, minutes=None):
    """F5 không reset đồng hồ, không gọi lại AI: có lượt đang mở thì dùng lại."""
    att = get_open_attempt(kind, ref_id)
    if att:
        return att
    questions = make_questions()          # có thể raise AIUnavailable -> chưa tạo gì cả
    return start_attempt(kind, ref_id, questions, minutes)


def minutes_left(att, default=60):
    if not att.deadline:
        return default
    secs = (att.deadline - datetime.utcnow()).total_seconds()
    return max(1, math.ceil(secs / 60))


def finish_attempt(att):
    """Gọi TRƯỚC db.session.commit() của Submission để cùng một transaction."""
    att.submitted_at = datetime.utcnow()
    session.pop(_key(att.kind, att.ref_id), None)


def grade_mcq(questions, form):
    """MỘT công thức chấm cho cả bài tập, bài kiểm tra, đề AI: điểm = đúng * 10 / TỔNG số câu."""
    review, correct, answered = [], 0, 0
    for idx, q in enumerate(questions):
        selected = (form.get(f"q_{idx}") or "").strip().upper()
        actual = (q.get("answer") or "").strip().upper()
        if selected in LETTERS:
            answered += 1
        ok = selected in LETTERS and selected == actual
        correct += ok
        review.append({
            "index": idx + 1, "question": q.get("question", ""),
            "options": q.get("options", []), "selected": selected,
            "correct": actual, "is_correct": ok,
            "difficulty": q.get("difficulty", "Trung bình"),
            "explanation": q.get("explanation", ""),
        })
    total = len(questions)
    score = round(correct * 10 / total, 2) if total else 0
    return review, correct, answered, total, score
