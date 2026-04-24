"""
NPIDE - Gap detection engine.

Uses lightweight Python + NumPy feature engineering so the project can run
without Polars, while keeping the IsolationForest-based anomaly logic.
"""

import math
import time
from pathlib import Path

import joblib
import numpy as np

from backend.data_layer.cache import cache_get, cache_set
from backend.data_layer.queries import get_gap_detection, stream_district_stats


MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "isolation_forest.pkl"
ISO_MODEL = None

FEATURE_COLS = [
    "gap_ratio",
    "per_capita_gap",
    "scheme_density",
    "log_population",
    "gap_squared",
    "coverage_rate",
]


def _load_model():
    global ISO_MODEL
    if MODEL_PATH.exists():
        try:
            ISO_MODEL = joblib.load(MODEL_PATH)
            print("[GAP] IsolationForest model loaded.")
        except Exception as e:
            print(f"[GAP] Model load failed: {e}. Using rule-based fallback.")
            ISO_MODEL = None
    else:
        print("[GAP] No trained model found. Using rule-based gap scoring.")
        ISO_MODEL = None


def engineer_gap_features(records: list[dict]) -> list[dict]:
    engineered = []
    for row in records:
        expected = float(row.get("expected", 0) or 0)
        actual = float(row.get("actual", 0) or 0)
        population = float(row.get("population", 0) or 0)
        schemes_available = float(row.get("schemes_available", 0) or 0)

        gap_ratio = (expected - actual) / (expected + 1)
        per_capita_gap = (expected - actual) / (population + 1)
        scheme_density = schemes_available / (population / 1000 + 1)
        log_population = math.log10(population + 1)
        gap_squared = gap_ratio ** 2
        coverage_rate = actual / (expected + 1)

        engineered.append(
            {
                **row,
                "expected": expected,
                "actual": actual,
                "population": population,
                "schemes_available": schemes_available,
                "gap_ratio": gap_ratio,
                "per_capita_gap": per_capita_gap,
                "scheme_density": scheme_density,
                "log_population": log_population,
                "gap_squared": gap_squared,
                "coverage_rate": coverage_rate,
            }
        )
    return engineered


def _feature_matrix(records: list[dict]) -> np.ndarray:
    if not records:
        return np.empty((0, len(FEATURE_COLS)))
    return np.array([[float(row.get(col, 0) or 0) for col in FEATURE_COLS] for row in records], dtype=float)


def _rule_based_gap_score(records: list[dict]) -> list[dict]:
    results = []
    for row in records:
        gap_ratio = float(row.get("gap_ratio", 0) or 0)
        results.append(
            {
                **row,
                "anomaly_score": -0.5,
                "is_anomaly": gap_ratio > 0.5,
                "severity_pct": gap_ratio * 100,
            }
        )
    return results


def detect_gaps(location: str = None) -> list[dict]:
    critical: list[dict] = []

    for chunk in stream_district_stats(location):
        if not chunk:
            continue

        engineered = engineer_gap_features(chunk)

        if ISO_MODEL is not None:
            features_np = _feature_matrix(engineered)
            scores = ISO_MODEL.score_samples(features_np)
            labels = ISO_MODEL.predict(features_np)

            score_min, score_max = scores.min(), scores.max()
            severity = (1 - (scores - score_min) / (score_max - score_min + 1e-9)) * 100

            evaluated = []
            for row, score, label, severity_pct in zip(engineered, scores, labels, severity):
                evaluated.append(
                    {
                        **row,
                        "anomaly_score": float(score),
                        "is_anomaly": bool(label == -1),
                        "severity_pct": float(severity_pct),
                    }
                )
        else:
            evaluated = _rule_based_gap_score(engineered)

        for row in evaluated:
            if row.get("is_anomaly"):
                critical.append(row)

    critical.sort(key=lambda x: x.get("severity_pct", 0), reverse=True)
    return critical


def get_gap_summary(location: str = None) -> dict:
    cache_key = f"gap_summary:{location or 'ALL'}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    ai_gaps = detect_gaps(location)
    db_gaps = get_gap_detection()

    result = {
        "location": location or "All",
        "total_anomalous_schemes": len(ai_gaps),
        "top_gaps": ai_gaps[:10],
        "db_gap_report": db_gaps[:15],
        "computed_at": time.time(),
    }
    cache_set(cache_key, result, ttl_seconds=300)
    return result


def train_isolation_forest(location: str = None) -> str:
    from sklearn.ensemble import IsolationForest

    all_features = []
    for chunk in stream_district_stats(location):
        if not chunk:
            continue
        engineered = engineer_gap_features(chunk)
        matrix = _feature_matrix(engineered)
        if len(matrix):
            all_features.append(matrix)

    if not all_features:
        return "No data available for training."

    X = np.vstack(all_features)

    model = IsolationForest(
        n_estimators=150,
        max_samples="auto",
        contamination=0.1,
        random_state=42,
        n_jobs=1,
    )
    model.fit(X)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    _load_model()
    return f"IsolationForest trained on {len(X)} scheme-location pairs."


_load_model()
