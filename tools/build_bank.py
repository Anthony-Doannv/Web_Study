"""Sinh lại ngân hàng đề chương bằng Gemini, bám nội dung bài học, có bước tự kiểm tra đáp án.
Chạy:  python -m tools.build_bank --subject Toán --grade 10          (thử 1 môn / 1 khối trước)
       python -m tools.build_bank --grade 10 --sleep 8               (cả khối, chậm cho đỡ 429)
Chạy lại được nhiều lần: đề đã 'approved' hoặc đã được AI sinh (source=ai) sẽ bị bỏ qua.
"""
import argparse
import time

from app import create_app
from app.extensions import db
from app.models import Lesson, Subject, Test
from app.services.ai_quiz import AIUnavailable, generate_quick_quiz, verify_by_resolving

TARGET, MIN_KEEP = 30, 25


def build_chapter_test(lesson, test, sleep):
    qs = generate_quick_quiz(lesson.subject.name, lesson.grade_level, lesson.chapter,
                             topic_hint=lesson.title, count=TARGET + 5, source_text=lesson.content)
    time.sleep(sleep)
    qs = verify_by_resolving(qs)                      # chỉ giữ câu mà AI giải lại ra cùng đáp án
    if len(qs) < MIN_KEEP:
        raise AIUnavailable(f"chỉ còn {len(qs)} câu sau khi kiểm tra đáp án")
    for x in qs: x["source"] = "ai"
    test.set_question_bank(qs[:TARGET])
    test.review_status = "draft"                      # chờ giáo viên duyệt
    db.session.commit()
    return len(qs[:TARGET])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject"); ap.add_argument("--grade", type=int); ap.add_argument("--sleep", type=float, default=6)
    a = ap.parse_args()
    app = create_app()
    with app.app_context():
        q = Lesson.query.join(Subject)
        if a.subject: q = q.filter(Subject.name == a.subject)
        if a.grade:   q = q.filter(Lesson.grade_level == a.grade)
        ok = fail = skip = 0
        for lesson in q.order_by(Lesson.subject_id, Lesson.grade_level, Lesson.chapter):
            test = Test.query.filter_by(subject_id=lesson.subject_id, grade_level=lesson.grade_level,
                                        chapter=lesson.chapter, test_type="chapter").first()
            if not test or test.review_status == "approved":
                skip += 1; continue
            if test.review_status == "draft" and test.get_question_bank() and test.get_question_bank()[0].get("source") == "ai":
                skip += 1; continue
            try:
                n = build_chapter_test(lesson, test, a.sleep)
                ok += 1; print(f"OK   {lesson.subject.name} {lesson.grade_level} ch{lesson.chapter}: {n} câu")
            except AIUnavailable as e:
                fail += 1; print(f"FAIL {lesson.subject.name} {lesson.grade_level} ch{lesson.chapter}: {e}")
            time.sleep(a.sleep)
        print(f"xong: ok={ok} fail={fail} skip={skip}")


if __name__ == "__main__":
    main()
