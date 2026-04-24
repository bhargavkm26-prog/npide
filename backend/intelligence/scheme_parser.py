"""
NPIDE - Scheme text extraction helpers.

Uses lightweight heuristics so the admin workflow can extract a draft scheme
record without relying on a hosted model or direct browser-side API calls.
"""

from __future__ import annotations

import re
from io import BytesIO


STATE_NAMES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya",
    "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim",
    "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand",
    "West Bengal", "Delhi",
]

OCCUPATION_KEYWORDS = {
    "farmer": "Farmer",
    "student": "Student",
    "self-employed": "Self-employed",
    "self employed": "Self-employed",
    "daily wage": "Daily Wage",
    "labour": "Daily Wage",
    "labor": "Daily Wage",
    "worker": "Daily Wage",
}


def _extract_text(filename: str, content_type: str, payload: bytes) -> str:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix == "pdf" or "pdf" in content_type:
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(payload))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="ignore")


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_name(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:20]:
        if re.search(r"\b(scheme|yojana|mission|programme|program)\b", line, re.I):
            return line[:200]
    match = re.search(r"([A-Z][A-Za-z0-9&(),.\-'\"]{4,}(?:Scheme|Yojana|Mission|Programme|Program))", text, re.I)
    if match:
        return match.group(1).strip()[:200]
    return (lines[0] if lines else "Untitled Scheme")[:200]


def _extract_description(text: str, name: str) -> str:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", _compact(text)) if s.strip()]
    for sentence in sentences:
        if sentence != name:
            return sentence[:300]
    return f"Eligibility-driven scheme record extracted from {name}."


def _extract_income(text: str) -> tuple[int, int]:
    compact = _compact(text).lower()
    between = re.search(r"income(?:\s+\w+){0,4}\s+between\s+rs\.?\s*([\d,]+)\s+(?:and|to|-)\s+rs\.?\s*([\d,]+)", compact)
    if between:
        return int(between.group(1).replace(",", "")), int(between.group(2).replace(",", ""))
    upper = re.search(r"(?:income(?:\s+\w+){0,4}\s+(?:below|under|up to|upto|not exceeding|less than)|annual income(?:\s+\w+){0,3}\s+(?:below|under|up to|upto|not exceeding|less than))\s+rs\.?\s*([\d,]+)", compact)
    if upper:
        return 0, int(upper.group(1).replace(",", ""))
    return 0, 999999999


def _extract_age(text: str) -> tuple[int, int]:
    compact = _compact(text).lower()
    between = re.search(r"(?:age|aged)\s+(?:between\s+)?(\d{1,3})\s+(?:and|to|-)\s+(\d{1,3})", compact)
    if between:
        return int(between.group(1)), int(between.group(2))
    minimum = re.search(r"(?:age|aged)\s+(?:above|over|at least)\s+(\d{1,3})", compact)
    maximum = re.search(r"(?:age|aged)\s+(?:below|under|up to|upto)\s+(\d{1,3})", compact)
    min_age = int(minimum.group(1)) if minimum else 0
    max_age = int(maximum.group(1)) if maximum else 120
    return min_age, max_age


def _extract_gender(text: str) -> str:
    compact = _compact(text).lower()
    if re.search(r"\b(women|woman|female|girl)\b", compact):
        return "Female"
    if re.search(r"\b(men|man|male|boy)\b", compact):
        return "Male"
    return "All"


def _extract_location(text: str) -> str:
    for state in STATE_NAMES:
        if re.search(rf"\b{re.escape(state)}\b", text, re.I):
            return state
    return "All"


def _extract_occupation(text: str) -> str:
    compact = _compact(text).lower()
    for keyword, value in OCCUPATION_KEYWORDS.items():
        if keyword in compact:
            return value
    return "All"


def _extract_benefit(text: str) -> int | None:
    compact = _compact(text).lower()
    patterns = [
        r"(?:benefit|assistance|subsidy|grant|aid|support|amount)\D{0,20}rs\.?\s*([\d,]+)",
        r"rs\.?\s*([\d,]+)\D{0,20}(?:benefit|assistance|subsidy|grant|aid|support|amount)",
    ]
    for pattern in patterns:
        match = re.search(pattern, compact)
        if match:
            return int(match.group(1).replace(",", ""))
    return None


def extract_scheme_from_upload(filename: str, content_type: str, payload: bytes) -> dict:
    text = _extract_text(filename, content_type, payload)
    name = _extract_name(text)
    min_income, max_income = _extract_income(text)
    min_age, max_age = _extract_age(text)
    return {
        "name": name,
        "description": _extract_description(text, name),
        "min_income": min_income,
        "max_income": max_income,
        "gender": _extract_gender(text),
        "location": _extract_location(text),
        "occupation": _extract_occupation(text),
        "min_age": min_age,
        "max_age": max_age,
        "benefit": _extract_benefit(text),
        "active": True,
    }
