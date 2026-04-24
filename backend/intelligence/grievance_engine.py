"""
NPIDE — Grievance Intelligence Engine
=======================================
Classifies citizen complaints using:
  1. spaCy for lightweight NLP feature extraction (~8 ms on CPU)
  2. RandomForest (calibrated) for category classification
  3. Keyword scoring for priority/escalation

Why NOT fine-tuned BERT?
  440 MB vs 12 MB; 200 ms vs 10 ms; no meaningful accuracy gain
  for the short complaint texts used in govt grievance portals.

Why NOT LLM?
  2–10 seconds per request; API cost; non-deterministic (not auditable).

Fallback: If spaCy/model not installed, uses keyword-only classification.
          System stays functional during demo setup.
"""

import hashlib
import re
import time
from pathlib import Path

from backend.data_layer.cache import cache_get, cache_set
from backend.data_layer.queries import get_grievance_hotspots, get_corruption_cases

# ── Try loading heavy dependencies gracefully ─────────────────
try:
    import spacy
    NLP = spacy.load("en_core_web_sm", disable=["parser", "ner"])
    SPACY_AVAILABLE = True
except Exception:
    NLP = None
    SPACY_AVAILABLE = False
    print("[GRIEVANCE] spaCy not available. Using keyword fallback.")

try:
    import joblib
    import numpy as np
    _model_path = Path(__file__).resolve().parent.parent / "models" / "grievance_pipeline.pkl"
    GRIEVANCE_CLF = joblib.load(_model_path) if _model_path.exists() else None
    if GRIEVANCE_CLF:
        print("[GRIEVANCE] RandomForest classifier loaded.")
    else:
        print("[GRIEVANCE] No trained classifier found. Using keyword fallback.")
except Exception as e:
    GRIEVANCE_CLF = None
    print(f"[GRIEVANCE] Classifier load failed: {e}")


# ── Constants ─────────────────────────────────────────────────

GRIEVANCE_CATEGORIES = [
    "delay",
    "corruption",
    "wrong_rejection",
    "no_awareness",
    "officer_misconduct",
    "portal_technical",
    "other",
]

# Maps DB category values → our classification labels
DB_TO_CATEGORY = {
    "delay": "delay",
    "corruption": "corruption",
    "wrong rejection": "wrong_rejection",
    "no awareness": "no_awareness",
}

ROUTING = {
    "delay":             "Finance Department",
    "corruption":        "Vigilance / Anti-Corruption Cell",
    "wrong_rejection":   "District Collectorate – Review Unit",
    "no_awareness":      "Scheme Awareness & Outreach Wing",
    "officer_misconduct":"Vigilance Department",
    "portal_technical":  "NIC / IT Support Desk",
    "other":             "Grievance Cell – General",
}

# Keyword → priority weight
PRIORITY_KEYWORDS: dict[str, int] = {
    "urgent": 3, "dying": 5, "starving": 5, "illegal": 4,
    "bribe": 5, "corrupt": 5, "months": 2, "years": 3,
    "repeated": 2, "fraud": 4, "delay": 1, "rejected": 2,
    "not received": 3, "no payment": 3,
}

# Keyword → category (fallback classifier)
KEYWORD_CATEGORY: dict[str, str] = {
    "bribe": "corruption", "corrupt": "corruption", "paid money": "corruption",
    "delay": "delay", "not received": "delay", "waiting": "delay", "months": "delay",
    "rejected": "wrong_rejection", "wrong": "wrong_rejection", "error": "wrong_rejection",
    "unaware": "no_awareness", "didn't know": "no_awareness", "no information": "no_awareness",
    "website": "portal_technical", "portal": "portal_technical", "app": "portal_technical",
    "officer": "officer_misconduct", "official": "officer_misconduct",
}


# ── Feature Extraction ────────────────────────────────────────

def _extract_features_spacy(text: str) -> dict:
    """spaCy-based feature extraction — ~8 ms on CPU."""
    doc = NLP(text.lower())
    tokens = [t.lemma_ for t in doc if not t.is_stop and not t.is_punct]
    priority_score = sum(
        score for kw, score in PRIORITY_KEYWORDS.items()
        if kw in text.lower()
    )
    return {
        "token_count": len(tokens),
        "has_amount":  any(t.like_num for t in doc),
        "priority":    min(priority_score, 10),
        "char_len":    len(text),
        "tokens":      tokens,
    }


def _extract_features_keyword(text: str) -> dict:
    """Fallback feature extraction — no external deps."""
    text_lower = text.lower()
    priority_score = sum(
        score for kw, score in PRIORITY_KEYWORDS.items()
        if kw in text_lower
    )
    words = re.findall(r'\b\w+\b', text_lower)
    has_amount = any(c.isdigit() for c in text)
    return {
        "token_count": len(words),
        "has_amount":  has_amount,
        "priority":    min(priority_score, 10),
        "char_len":    len(text),
        "tokens":      words,
    }


def _classify_by_keyword(text: str) -> tuple[str, float]:
    """Keyword-based fallback classifier. Returns (category, confidence)."""
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for kw, cat in KEYWORD_CATEGORY.items():
        if kw in text_lower:
            scores[cat] = scores.get(cat, 0) + 1
    if scores:
        best = max(scores, key=lambda k: scores[k])
        total = sum(scores.values())
        return best, round(scores[best] / total, 2)
    return "other", 0.3


def _normalize_category(label: str) -> str:
    category = str(label).strip().lower().replace(" ", "_")
    return category if category in ROUTING else "other"


# ── Public API ────────────────────────────────────────────────

def classify_grievance(raw_text: str) -> dict:
    """
    Classify a citizen complaint into:
      - category   : what type of problem
      - priority   : 0 (low) → 10 (critical)
      - confidence : 0–1
      - route_to   : which department to route to
      - escalate   : True if needs immediate attention

    Pipeline: spaCy features → RandomForest OR keyword fallback
    Latency: ~12 ms (spaCy+ML), ~1 ms (keyword fallback), ~0.2 ms (cache)
    """
    # Cache hit
    cache_key = f"griev:{hashlib.md5(raw_text.encode()).hexdigest()}"
    cached = cache_get(cache_key)
    if cached:
        return {**cached, "source": "cache"}

    # Feature extraction
    if SPACY_AVAILABLE:
        feats = _extract_features_spacy(raw_text)
    else:
        feats = _extract_features_keyword(raw_text)

    # Classification
    if GRIEVANCE_CLF is not None:
        try:
            proba = GRIEVANCE_CLF.predict_proba([raw_text])[0]
            cat_idx = int(np.argmax(proba))
            classes = GRIEVANCE_CLF.classes_
            category = _normalize_category(classes[cat_idx])
            confidence = float(proba[cat_idx])
        except Exception:
            category, confidence = _classify_by_keyword(raw_text)
    else:
        category, confidence = _classify_by_keyword(raw_text)

    result = {
        "category":   category,
        "confidence": round(confidence, 3),
        "priority":   feats["priority"],
        "route_to":   ROUTING.get(category, "Grievance Cell"),
        "escalate":   feats["priority"] >= 3 or confidence < 0.5,
        "source":     "computed",
    }

    cache_set(cache_key, result, ttl_seconds=3600)
    return result


def batch_classify(grievances: list[dict]) -> list[dict]:
    """
    Classify a list of grievances. Each item: {"id": ..., "text": ..., "location": ...}
    Returns sorted by priority DESC (most urgent first).
    """
    results = []
    for g in grievances:
        clf = classify_grievance(g.get("description", g.get("text", "")))
        results.append({
            "grievance_id": g.get("grievance_id", g.get("id")),
            "location":     g.get("location"),
            **clf,
        })
    results.sort(key=lambda x: x["priority"], reverse=True)
    return results


def get_hotspot_report() -> dict:
    """
    Returns grievance hotspot data from DB + corruption analysis.
    Used by the government dashboard.
    """
    cache_key = "hotspot:report"
    cached = cache_get(cache_key)
    if cached:
        return cached

    hotspots    = get_grievance_hotspots()
    corruption  = get_corruption_cases()

    result = {
        "hotspots":   hotspots,
        "corruption": corruption,
        "computed_at": time.time(),
    }
    cache_set(cache_key, result, ttl_seconds=180)  # 3 min freshness
    return result


# ── Model Training (run offline) ─────────────────────────────

def train_grievance_classifier(labeled_csv_path: str) -> str:
    """
    Train RandomForest grievance classifier.
    Input CSV: columns [text, category]
    Run as offline job — NOT during serving.
    """
    import csv
    import joblib
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import Pipeline
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report
    from pathlib import Path

    texts, labels = [], []
    with open(labeled_csv_path) as f:
        for row in csv.DictReader(f):
            texts.append(row["text"])
            labels.append(row["category"])

    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=10_000,
            sublinear_tf=True,
        )),
        ("clf", CalibratedClassifierCV(
            RandomForestClassifier(
                n_estimators=200, max_depth=12,
                class_weight="balanced", n_jobs=-1, random_state=42,
            ),
            method="sigmoid", cv=5,
        )),
    ])
    pipeline.fit(X_train, y_train)
    preds = pipeline.predict(X_test)
    report = classification_report(y_test, preds, target_names=GRIEVANCE_CATEGORIES)

    path = Path("backend/models/grievance_pipeline.pkl")
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, path)
    return f"Classifier trained.\n{report}"
