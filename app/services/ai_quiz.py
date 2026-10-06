"""Sinh đề bằng Gemini: structured output + validate chặt. KHÔNG có fallback câu giả."""
import random
import re

from pydantic import BaseModel

from .ai_service import clean_ai_text, _get_api_key

MODEL = "gemini-3.1-flash-lite"
LETTERS = ["A", "B", "C", "D"]


class AIUnavailable(Exception):
    """Gemini lỗi / hết quota / trả đề không đạt chuẩn. Caller KHÔNG được lưu gì cả."""


class QuizItem(BaseModel):
    question: str
    options: list[str]
    answer: str
    explanation: str


class Solved(BaseModel):
    answer: str


def call_json(prompt, schema, temperature=0.6, retries=2):
    api_key = _get_api_key()
    if not api_key:
        raise AIUnavailable("Chưa cấu hình GEMINI_API_KEY.")
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=60_000))  # ms
    last = None
    for _ in range(retries):
        try:
            resp = client.models.generate_content(
                model=MODEL, contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=list[schema], temperature=temperature),
            )
            if resp.parsed:
                return resp.parsed
        except Exception as exc:            # 429, timeout, 5xx...
            last = exc
    raise AIUnavailable(f"Gemini không phản hồi hợp lệ: {type(last).__name__ if last else 'rỗng'}")


_REF_OPTION = re.compile(r"\b[A-D]\s*(và|,|/)\s*[A-D]\b")      # "Cả A và B" -> không xáo được


def validate_questions(items, count, min_ratio=0.8, rng=None):
    rng = rng or random.Random()
    good, seen = [], set()
    for it in items:
        q = clean_ai_text(it.question).strip()
        opts = [clean_ai_text(o).strip() for o in it.options]
        ans = (it.answer or "").strip().upper()[:1]
        if len(q) < 15 or len(opts) != 4 or not all(opts):
            continue
        if len({o.lower() for o in opts}) != 4 or ans not in LETTERS:
            continue
        if q.lower() in seen or any(_REF_OPTION.search(o) for o in opts):
            continue
        seen.add(q.lower())
        correct_text = opts[LETTERS.index(ans)]
        rng.shuffle(opts)                              # AI hay đặt đáp án đúng ở B/C
        good.append({
            "question": q, "options": opts,
            "answer": LETTERS[opts.index(correct_text)],
            "explanation": clean_ai_text(it.explanation),
        })
    if len(good) < int(count * min_ratio):
        raise AIUnavailable(f"Chỉ có {len(good)}/{count} câu đạt chuẩn.")
    return good[:count]


def verify_by_resolving(questions):
    """Cho Gemini tự giải lại từng câu (KHÔNG đưa đáp án). Chỉ giữ câu trùng đáp án."""
    listing = "\n\n".join(
        f"Câu {i+1}: {q['question']}\n" + "\n".join(f"{LETTERS[j]}. {o}" for j, o in enumerate(q["options"]))
        for i, q in enumerate(questions))
    prompt = ("Giải lần lượt từng câu trắc nghiệm sau. Trả về danh sách đúng thứ tự, "
              "mỗi phần tử chỉ chứa answer là A, B, C hoặc D.\n\n" + listing)
    solved = call_json(prompt, Solved, temperature=0.0)
    if len(solved) != len(questions):
        raise AIUnavailable("Bước kiểm tra đáp án trả sai số lượng.")
    return [q for q, s in zip(questions, solved)
            if (s.answer or "").strip().upper()[:1] == q["answer"]]


_RULES = ("Mỗi câu có đúng 4 lựa chọn, chỉ 1 đáp án đúng, 3 đáp án nhiễu phải hợp lý (sai ở lỗi học sinh hay gặp). "
          "Viết văn bản thuần, dùng ký hiệu Unicode (≤, ≥, ², √, ∈) thay cho LaTeX. "
          "Không viết kiểu 'Phương án đúng theo lý thuyết'. Giải thích ngắn 1-2 câu.")


def generate_quick_quiz(subject_name, grade_level=None, chapter=None, topic_hint=None,
                        count=30, avoid_material=None, source_text=None):
    """Giữ nguyên chữ ký cũ + thêm source_text (nội dung bài học để bám sát)."""
    avoid = " | ".join((avoid_material or [])[:6])
    prompt = (f"Tạo đúng {count} câu trắc nghiệm môn {subject_name} lớp {grade_level or ''}, "
              f"chương {chapter or 'bất kỳ'}, chủ đề {topic_hint or 'theo nội dung chương'}. "
              "Độ khó từ nhận biết đến vận dụng, câu hỏi phải có số liệu / tình huống cụ thể, không hỏi chung chung. "
              + _RULES + (f"\nTránh trùng ý với: {avoid}" if avoid else "")
              + (f"\n\nBám sát nội dung bài học sau:\n{source_text[:6000]}" if source_text else ""))
    return validate_questions(call_json(prompt, QuizItem), count)


def generate_exercise_quiz(subject_name, exercise_title, exercise_content,
                           grade_level=None, chapter=None, count=12):
    prompt = (f"Tạo đúng {count} câu trắc nghiệm luyện tập môn {subject_name} lớp {grade_level or ''}, "
              f"chương {chapter or ''}, dựa trên bài tập '{exercise_title}'. Thiên về luyện tập, vận dụng ngắn. "
              + _RULES + f"\n\nNội dung bài tập:\n{exercise_content[:4000]}")
    return validate_questions(call_json(prompt, QuizItem), count)
