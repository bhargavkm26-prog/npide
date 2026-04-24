"""
NPIDE - Model training script.

Creates the local demo models used by the backend.
"""

import os
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT_ROOT / "backend" / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def train_isolation_forest():
    print("[TRAIN] Training IsolationForest for gap detection...")

    try:
        from backend.data_layer.queries import stream_district_stats
        from backend.intelligence.gap_detector import engineer_gap_features, _feature_matrix

        all_features = []
        for chunk in stream_district_stats():
            if not chunk:
                continue
            engineered = engineer_gap_features(chunk)
            matrix = _feature_matrix(engineered)
            if len(matrix):
                all_features.append(matrix)

        if all_features:
            X = np.vstack(all_features)
            print(f"[TRAIN] Using real DB data: {len(X)} scheme-location pairs.")
        else:
            raise ValueError("No data from DB")

    except Exception as e:
        print(f"[TRAIN] DB not available ({e}). Using synthetic training data.")
        np.random.seed(42)
        n = 200
        X = np.column_stack([
            np.random.beta(2, 5, n),
            np.random.exponential(0.01, n),
            np.random.uniform(0.5, 5.0, n),
            np.random.normal(4.5, 0.8, n),
            np.random.beta(2, 8, n) ** 2,
            1 - np.random.beta(2, 5, n),
        ])

    model = IsolationForest(
        n_estimators=150,
        max_samples="auto",
        contamination=0.1,
        random_state=42,
        n_jobs=1,
    )
    model.fit(X)
    path = MODEL_DIR / "isolation_forest.pkl"
    joblib.dump(model, path)
    print(f"[TRAIN] IsolationForest saved -> {path}")
    return True


def train_grievance_classifier():
    print("[TRAIN] Training grievance classifier...")

    texts, labels = [], []
    try:
        from backend.data_layer.database import engine
        from sqlalchemy import text

        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT description, category FROM grievances
                WHERE description IS NOT NULL AND category IS NOT NULL
            """)).fetchall()

        for row in rows:
            texts.append(row[0])
            labels.append(row[1].replace(" ", "_"))

        print(f"[TRAIN] Loaded {len(texts)} grievances from DB.")
    except Exception as e:
        print(f"[TRAIN] DB not available ({e}). Using synthetic training data.")

    synthetic = [
        ("My payment has not arrived for 3 months", "delay"),
        ("MGNREGA wages delayed by 6 months", "delay"),
        ("PM Kisan amount not credited since last year", "delay"),
        ("Pension not received for 4 months continuously", "delay"),
        ("Subsidy disbursement is taking too long", "delay"),
        ("Application pending approval for 8 months", "delay"),
        ("No payment received despite approval letter", "delay"),
        ("Amount transferred but never reached my account", "delay"),
        ("Officer asked for bribe to process my application", "corruption"),
        ("Local official demanded money for PM Kisan approval", "corruption"),
        ("Panchayat member selling MGNREGA job cards illegally", "corruption"),
        ("Agent demanded Rs 2000 to submit my documents", "corruption"),
        ("Corrupt official rejected my valid application", "corruption"),
        ("Bribe demanded at government office for scheme enrollment", "corruption"),
        ("Middleman charging fees for free government scheme", "corruption"),
        ("Official threatening to reject unless paid money", "corruption"),
        ("Application rejected without any reason given", "wrong_rejection"),
        ("MGNREGA rejected despite being eligible according to rules", "wrong_rejection"),
        ("PM Kisan application denied wrongly", "wrong_rejection"),
        ("Rejected due to wrong information entered by officer", "wrong_rejection"),
        ("My valid documents were rejected", "wrong_rejection"),
        ("Scheme benefits denied despite fulfilling all criteria", "wrong_rejection"),
        ("Error in system caused my rejection unfairly", "wrong_rejection"),
        ("Was not aware this scheme existed for 2 years", "no_awareness"),
        ("Nobody informed me about PM Kisan scheme", "no_awareness"),
        ("Villagers still do not know about this benefit", "no_awareness"),
        ("No information given at gram panchayat level", "no_awareness"),
        ("Scheme existed for years but we were never told", "no_awareness"),
        ("Lack of awareness in our district about government benefits", "no_awareness"),
        ("Government officer was rude and refused to help", "officer_misconduct"),
        ("Official misbehaved with my wife at the office", "officer_misconduct"),
        ("Block officer not available for months", "officer_misconduct"),
        ("Official not processing applications despite being in office", "officer_misconduct"),
        ("Website not working when trying to apply online", "portal_technical"),
        ("Portal gives error 500 when uploading Aadhaar", "portal_technical"),
        ("App crashes during OTP verification step", "portal_technical"),
        ("Unable to login to government portal for weeks", "portal_technical"),
        ("Online form not submitting, keeps timing out", "portal_technical"),
        ("I want to know more about available schemes", "other"),
        ("Need help with my application process", "other"),
        ("General inquiry about eligibility criteria", "other"),
    ]

    for text_sample, category in synthetic:
        texts.append(text_sample)
        labels.append(category)

    if len(texts) < 10:
        print("[TRAIN] Not enough data. Aborting.")
        return False

    label_map = {
        "delay": "delay",
        "wrong rejection": "wrong_rejection",
        "wrong_rejection": "wrong_rejection",
        "no awareness": "no_awareness",
        "no_awareness": "no_awareness",
        "corruption": "corruption",
        "officer_misconduct": "officer_misconduct",
        "portal_technical": "portal_technical",
        "other": "other",
    }
    labels = [label_map.get(label, "other") for label in labels]

    print(f"[TRAIN] Total training samples: {len(texts)}")

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=5000,
            sublinear_tf=True,
            min_df=1,
        )),
        ("clf", RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            class_weight="balanced",
            n_jobs=1,
            random_state=42,
        )),
    ])
    pipeline.fit(texts, labels)

    path = MODEL_DIR / "grievance_pipeline.pkl"
    joblib.dump(pipeline, path)
    print(f"[TRAIN] Grievance classifier saved -> {path}")

    test_cases = [
        ("My payment has not come for 3 months", "delay"),
        ("Officer demanded bribe", "corruption"),
        ("Application was rejected wrongly", "wrong_rejection"),
    ]
    print("\n[TRAIN] Self-test results:")
    for text_sample, expected in test_cases:
        pred = pipeline.predict([text_sample])[0]
        status = "OK" if pred == expected else "CHECK"
        print(f"  {status} '{text_sample[:40]}...' -> {pred} (expected: {expected})")

    return True

def train_predictor():
    print("[TRAIN] Training district failure predictor...")

    try:
        from backend.data_layer.database import engine
        from sqlalchemy import text
        import pandas as pd

        df = pd.read_sql("""
            SELECT district, month, expected, actual, population, schemes
            FROM district_monthly
            ORDER BY district, month
        """, engine)

    except Exception as e:
        print(f"[TRAIN] DB not available ({e})")
        return False

    # 🔷 FEATURES
    df["gap_ratio"] = (df["expected"] - df["actual"]) / (df["expected"] + 1)
    df["coverage_rate"] = df["actual"] / (df["expected"] + 1)
    df["scheme_density"] = df["schemes"] / (df["population"] / 1000 + 1)

    df["trend"] = df.groupby("district")["gap_ratio"].diff().fillna(0)

    # 🔷 LABEL
    df["next_gap"] = df.groupby("district")["gap_ratio"].shift(-1)
    df["label"] = (df["next_gap"] > 0.4).astype(int)

    df = df.dropna()

    X = df[["gap_ratio", "coverage_rate", "scheme_density", "trend"]]
    y = df["label"]

    from sklearn.ensemble import GradientBoostingClassifier

    model = GradientBoostingClassifier(n_estimators=200)
    model.fit(X, y)

    path = MODEL_DIR / "predictor.pkl"
    joblib.dump(model, path)

    print(f"[TRAIN] Predictor saved -> {path}")
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("  NPIDE - Model Training")
    print("=" * 60)

    ssuccess1 = train_isolation_forest()
    success2 = train_grievance_classifier()
    success3 = train_predictor()

    print("\n" + "=" * 60)
    if success1 and success2 and success3:
        print("ALL MODELS TRAINED SUCCESSFULLY")
    else:
        print("Some models failed")
    print("=" * 60)


