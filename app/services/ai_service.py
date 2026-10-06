import os
import json
import random
import re
import hashlib
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


def _get_api_key():
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def clean_ai_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r", "")
    replacements = {
        "\\subseteq": "⊆",
        "\\in": "∈",
        "\\notin": "∉",
        "\\le": "≤",
        "\\ge": "≥",
        "\\times": "×",
        "\\Delta": "Δ",
        "\\alpha": "α",
        "\\beta": "β",
        "\\gamma": "γ",
        "\\pi": "π",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", text)
    text = re.sub(r"\\sqrt\{([^{}]+)\}", r"√(\1)", text)
    text = re.sub(r"\$([^$]+)\$", r"\1", text)
    text = text.replace("\\(", "").replace("\\)", "")
    text = re.sub(r"^\s*\*\s+", "• ", text, flags=re.M)
    text = re.sub(r"^\s*\-\s+", "• ", text, flags=re.M)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()




def _seeded_rng(*parts) -> random.Random:
    seed_text = '||'.join(str(part or '').strip() for part in parts)
    digest = hashlib.sha256(seed_text.encode('utf-8')).hexdigest()
    return random.Random(int(digest[:16], 16))

def _fallback_chat(message: str, grade_level: int | None = None) -> str:
    return clean_ai_text(
        f"Chưa cấu hình Gemini API key. Gợi ý tạm cho học sinh lớp {grade_level or 'THPT'}: "
        f"Với câu hỏi '{message[:120]}', em hãy xác định kiến thức trọng tâm, xem ví dụ mẫu, rồi mới giải bài đầy đủ."
    )


def ask_ai(message: str, grade_level: int | None = None) -> str:
    api_key = _get_api_key()
    if not api_key:
        return _fallback_chat(message, grade_level)
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        prompt = (
            f"Bạn là gia sư AI cho học sinh lớp {grade_level or 'THPT'}. "
            "Trả lời bằng tiếng Việt, rõ ràng, sạch, không dùng markdown thừa, không dùng ký hiệu LaTeX nếu có thể. "
            f"Câu hỏi: {message}"
        )
        response = client.models.generate_content(model="gemini-3.1-flash-lite", contents=prompt)
        text = getattr(response, "text", None)
        return clean_ai_text(text or "Gemini không trả về nội dung.")
    except Exception as exc:
        return clean_ai_text(f"Lỗi khi gọi Gemini API: {exc}")


def grade_exercise(content: str, title: str) -> tuple[float, str]:
    api_key = _get_api_key()
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            prompt = f"""
Bạn là giáo viên chấm bài.
Hãy chấm bài làm sau theo thang điểm 10.
Trả lời đúng định dạng:
SCORE: <số điểm>
FEEDBACK: <nhận xét ngắn, tiếng Việt, sạch, không latex>

Tên bài: {title}
Bài làm:
{content}
""".strip()
            response = client.models.generate_content(model="gemini-3.1-flash-lite", contents=prompt)
            text = clean_ai_text((getattr(response, "text", "") or "").strip())
            score = 7.0
            feedback = text or "Gemini đã chấm bài."
            for line in text.splitlines():
                if line.upper().startswith("SCORE:"):
                    try:
                        score = float(line.split(":", 1)[1].strip())
                    except Exception:
                        pass
                if line.upper().startswith("FEEDBACK:"):
                    feedback = line.split(":", 1)[1].strip()
            return max(0.0, min(10.0, score)), clean_ai_text(feedback)
        except Exception as exc:
            return 0.0, clean_ai_text(f"Lỗi khi chấm bằng Gemini: {exc}")

    words = len((content or "").split())
    if words >= 120:
        return 9.0, "Chưa có Gemini key. Chấm tạm: bài làm khá đầy đủ, trình bày rõ."
    if words >= 60:
        return 7.5, "Chưa có Gemini key. Chấm tạm: bài làm đạt mức khá, nên bổ sung lập luận hoặc ví dụ."
    if words >= 20:
        return 6.0, "Chưa có Gemini key. Chấm tạm: bài làm còn ngắn, cần chi tiết hơn."
    return 4.5, "Chưa có Gemini key. Chấm tạm: bài làm quá ngắn, cần bổ sung nội dung."


def review_mcq_submission(title: str, subject_name: str, answered_count: int, total_count: int, correct_count: int, wrong_topics: list[str] | None = None) -> str:
    wrong_topics = wrong_topics or []
    score_10 = round((correct_count * 10 / answered_count), 2) if answered_count else 0
    api_key = _get_api_key()
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            prompt = f"""
Bạn là gia sư AI. Hãy nhận xét ngắn gọn cho bài làm trắc nghiệm của học sinh.
Trả lời đúng định dạng:
FEEDBACK: <nhận xét 2-4 câu, tiếng Việt, động viên + chỉ ra phần cần ôn>

Bài: {title}
Môn: {subject_name}
Số câu đã làm: {answered_count}/{total_count}
Số câu đúng: {correct_count}
Điểm quy đổi trên 10: {score_10}
Các câu/chủ đề cần xem lại: {', '.join(wrong_topics) if wrong_topics else 'Không nhiều lỗi rõ rệt'}
""".strip()
            response = client.models.generate_content(model="gemini-3.1-flash-lite", contents=prompt)
            text = clean_ai_text((getattr(response, "text", "") or "").strip())
            for line in text.splitlines():
                if line.upper().startswith("FEEDBACK:"):
                    return clean_ai_text(line.split(":", 1)[1].strip())
            if text:
                return text
        except Exception:
            pass

    if answered_count == 0:
        return "Bạn chưa chọn câu nào nên chưa có nhận xét."
    if score_10 >= 8.5:
        return "AI chấm tự động: Em làm khá tốt, nắm được phần lớn ý chính. Hãy xem lại vài câu sai để giữ độ chính xác ổn định hơn."
    if score_10 >= 6.5:
        return "AI chấm tự động: Em đã nắm được phần cơ bản. Nên ôn lại các câu sai và luyện thêm 1 lượt ngắn để tăng tốc độ làm bài."
    return "AI chấm tự động: Em cần xem lại kiến thức nền và làm lại các câu vừa sai. Nên học lại phần lý thuyết rồi luyện thêm câu dễ trước."


import re

def clean_plan_lines(value):
    if not value:
        return []

    if isinstance(value, list):
        raw_lines = value
    else:
        raw_lines = str(value).splitlines()

    cleaned = []
    for line in raw_lines:
        if line is None:
            continue
        line = str(line).strip()
        if not line:
            continue

        # bỏ bullet ở đầu dòng: -, •, *, 1. 2. ...
        line = re.sub(r'^\s*(?:[-•*]+|\d+\.)\s*', '', line).strip()

        if line:
            cleaned.append(line)

    return cleaned