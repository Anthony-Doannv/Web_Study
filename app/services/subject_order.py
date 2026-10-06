import unicodedata

SUBJECT_ORDER = [
    "toan", "ngu van", "tieng anh", "vat ly", "hoa hoc",
    "sinh hoc", "lich su", "dia ly", "giao duc cong dan"
]

SUBJECT_ALIAS_MAP = {
    "toan": "toan",
    "mon toan": "toan",
    "ngu van": "ngu van",
    "van": "ngu van",
    "mon van": "ngu van",
    "tieng anh": "tieng anh",
    "anh": "tieng anh",
    "mon anh": "tieng anh",
    "vat ly": "vat ly",
    "ly": "vat ly",
    "mon ly": "vat ly",
    "hoa hoc": "hoa hoc",
    "hoa": "hoa hoc",
    "mon hoa": "hoa hoc",
    "sinh hoc": "sinh hoc",
    "sinh": "sinh hoc",
    "mon sinh": "sinh hoc",
    "lich su": "lich su",
    "su": "lich su",
    "mon su": "lich su",
    "dia ly": "dia ly",
    "dia": "dia ly",
    "mon dia": "dia ly",
    "giao duc cong dan": "giao duc cong dan",
    "cong dan": "giao duc cong dan",
    "gdcd": "giao duc cong dan",
    "mon cong dan": "giao duc cong dan",
}

ORDER_INDEX = {name: idx for idx, name in enumerate(SUBJECT_ORDER)}


def _normalize_subject_name(name):
    text = unicodedata.normalize("NFD", str(name or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = " ".join(text.lower().strip().split())
    return SUBJECT_ALIAS_MAP.get(text, text)


def _canonical_subject_name(raw_name):
    normalized = _normalize_subject_name(raw_name)
    if normalized in ORDER_INDEX:
        return normalized
    for alias, canonical in SUBJECT_ALIAS_MAP.items():
        if normalized == alias or normalized.startswith(alias + " ") or (" " + alias + " ") in (" " + normalized + " "):
            return canonical
    for canonical in SUBJECT_ORDER:
        if canonical in normalized:
            return canonical
    return normalized


def subject_sort_key(subject_or_name):
    raw_name = getattr(subject_or_name, "name", subject_or_name)
    canonical = _canonical_subject_name(raw_name)
    return (ORDER_INDEX.get(canonical, 999), str(raw_name).lower())


def sort_subjects(subjects):
    return sorted(subjects, key=subject_sort_key)
