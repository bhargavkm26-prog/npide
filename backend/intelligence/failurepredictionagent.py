"""
District Welfare Scheme Failure Prediction System
==================================================
Steps:
  1. Synthetic district data (6 months)
  2. Feature engineering (gap_ratio, coverage_rate, scheme_density, trend)
  3. Label creation (1 = failed next month, 0 = normal)
  4. Gradient Boosting / Random Forest model
  5. Prediction with failure_probability + risk_level
  6. Alert agent via Anthropic Claude API (fires when probability > 0.7)

Requirements:
  pip install scikit-learn anthropic pandas numpy tabulate
"""

import math
import json
import random
import anthropic
import numpy as np
import pandas as pd
from tabulate import tabulate
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report


# ─────────────────────────────────────────────
# STEP 1 — INPUT DATA (synthetic 6-month DB)
# ─────────────────────────────────────────────

DISTRICTS = [
    {"name": "Raichur",        "population": 1924000, "schemes": 12},
    {"name": "Bidar",          "population": 1703000, "schemes": 9},
    {"name": "Yadgir",         "population": 1174000, "schemes": 7},
    {"name": "Kalaburagi",     "population": 2564000, "schemes": 14},
    {"name": "Koppal",         "population": 1391000, "schemes": 8},
    {"name": "Vijayapura",     "population": 2175000, "schemes": 11},
    {"name": "Bagalkot",       "population": 1888000, "schemes": 10},
    {"name": "Haveri",         "population": 1598000, "schemes": 13},
    {"name": "Gadag",          "population": 1064000, "schemes": 8},
    {"name": "Dharwad",        "population": 1847000, "schemes": 15},
    {"name": "Mysuru",         "population": 3001000, "schemes": 18},
    {"name": "Mandya",         "population": 1760000, "schemes": 11},
    {"name": "Hassan",         "population": 1776000, "schemes": 10},
    {"name": "Tumakuru",       "population": 2681000, "schemes": 13},
    {"name": "Bengaluru Rural","population":  990000, "schemes": 16},
]


def seeded_random(seed: int, low: float, high: float) -> float:
    """Deterministic pseudo-random in [low, high) using a sine hash."""
    val = math.sin(seed) * 43758.5453123
    frac = val - math.floor(val)
    return low + frac * (high - low)


def generate_history(district: dict, district_idx: int) -> list[dict]:
    """Generate 6 months of expected/actual beneficiary data for a district."""
    history = []
    for month in range(6):
        seed = district_idx * 100 + month * 7
        expected = int(seeded_random(seed + 1, 5000, 25000))
        noise    = seeded_random(seed + 2, 0.55, 1.0)
        actual   = int(expected * noise)
        history.append({
            "month":      month + 1,
            "expected":   expected,
            "actual":     actual,
            "population": district["population"],
            "schemes":    district["schemes"],
        })
    return history


# ─────────────────────────────────────────────
# STEP 2 — FEATURE ENGINEERING
# ─────────────────────────────────────────────

def engineer_features(history: list[dict]) -> dict:
    """
    Compute:
      gap_ratio      — average (expected - actual) / expected  [higher = worse]
      coverage_rate  — avg actual beneficiaries per 1000 population
      scheme_density — schemes per million population
      trend          — change in gap from month 1 → month 6 (positive = worsening)
    """
    gaps = [(h["expected"] - h["actual"]) / h["expected"] for h in history]

    gap_ratio      = sum(gaps) / len(gaps)
    coverage_rate  = sum(h["actual"] / h["population"] * 1000 for h in history) / len(history)
    scheme_density = history[0]["schemes"] / (history[0]["population"] / 1_000_000)
    trend          = gaps[-1] - gaps[0]   # positive = getting worse

    return {
        "gap_ratio":      round(gap_ratio,      4),
        "coverage_rate":  round(coverage_rate,  4),
        "scheme_density": round(scheme_density, 4),
        "trend":          round(trend,          4),
    }


# ─────────────────────────────────────────────
# STEP 3 — LABEL CREATION
# ─────────────────────────────────────────────

def create_label(features: dict) -> int:
    """
    Label = 1  (district will fail next month) when:
      - gap_ratio      > 0.30   (consistently delivering < 70% of expected)
      - coverage_rate  < 5.0    (very low beneficiary reach)
      - scheme_density < 10.0   (few schemes per million people)
      - trend          > 0.05   (worsening trajectory)
    Label = 0 otherwise.
    """
    score = 0
    if features["gap_ratio"]      > 0.30:  score += 1
    if features["coverage_rate"]  < 5.0:   score += 1
    if features["scheme_density"] < 10.0:  score += 1
    if features["trend"]          > 0.05:  score += 1
    return 1 if score >= 2 else 0


# ─────────────────────────────────────────────
# STEP 4 — BUILD DATASET & TRAIN MODEL
# ─────────────────────────────────────────────

def build_dataset() -> tuple[pd.DataFrame, list[str]]:
    """Build the feature matrix + labels for all districts."""
    rows = []
    for idx, district in enumerate(DISTRICTS):
        history  = generate_history(district, idx + 1)
        feats    = engineer_features(history)
        label    = create_label(feats)
        rows.append({
            "district":      district["name"],
            "gap_ratio":     feats["gap_ratio"],
            "coverage_rate": feats["coverage_rate"],
            "scheme_density":feats["scheme_density"],
            "trend":         feats["trend"],
            "label":         label,
        })
    return pd.DataFrame(rows)


def train_model(df: pd.DataFrame, model_type: str = "gradient_boosting"):
    """
    Train a Gradient Boosting or Random Forest classifier.
    Returns the fitted model.
    """
    FEATURE_COLS = ["gap_ratio", "coverage_rate", "scheme_density", "trend"]
    X = df[FEATURE_COLS].values
    y = df["label"].values

    # Because our dataset is small (15 rows) we train on all data;
    # for a real deployment you'd use train/test split + cross-validation.
    if model_type == "gradient_boosting":
        model = GradientBoostingClassifier(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=3,
            random_state=42,
        )
    else:
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=4,
            random_state=42,
        )

    model.fit(X, y)
    return model, FEATURE_COLS


# ─────────────────────────────────────────────
# STEP 5 — PREDICTION
# ─────────────────────────────────────────────

def predict_districts(model, feature_cols: list[str], df: pd.DataFrame) -> list[dict]:
    """
    Run predictions and return a list of:
      {
        "district": "Raichur",
        "failure_probability": 0.82,
        "risk_level": "HIGH"          # HIGH ≥ 0.7, MEDIUM ≥ 0.4, LOW < 0.4
      }
    sorted by failure_probability descending.
    """
    X = df[feature_cols].values
    probs = model.predict_proba(X)[:, 1]   # P(label=1)

    results = []
    for i, row in df.iterrows():
        prob = round(float(probs[i]), 4)
        risk = "HIGH" if prob >= 0.7 else ("MEDIUM" if prob >= 0.4 else "LOW")
        results.append({
            "district":            row["district"],
            "failure_probability": prob,
            "risk_level":          risk,
            "gap_ratio":           row["gap_ratio"],
            "coverage_rate":       row["coverage_rate"],
            "scheme_density":      row["scheme_density"],
            "trend":               "worsening" if row["trend"] > 0 else "improving",
        })

    results.sort(key=lambda x: x["failure_probability"], reverse=True)
    return results


# ─────────────────────────────────────────────
# STEP 6 — ALERT AGENT (Claude API)
# ─────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """You are a government welfare scheme monitoring agent for Karnataka, India.
You have access to ML predictions from a Gradient Boosting model trained on 6 months of district data.

PREDICTION RESULTS:
{predictions_json}

Feature definitions:
- gap_ratio:      avg (expected - actual) / expected  [higher = worse delivery]
- coverage_rate:  avg actual beneficiaries per 1000 population
- scheme_density: number of schemes per million population
- trend:          "worsening" if gap grew over 6 months, else "improving"

Your role:
1. Analyze HIGH risk districts (failure_probability > 0.7)
2. Recommend concrete government interventions
3. Prioritize by severity and feasibility
4. Be concise, data-driven, and actionable

Always back your recommendations with the specific feature values from the data above.
"""


def run_alert_agent(predictions: list[dict]) -> None:
    """
    For every district with failure_probability > 0.7,
    call the Claude API and print intervention recommendations.
    """
    high_risk = [p for p in predictions if p["failure_probability"] > 0.7]

    if not high_risk:
        print("\n✅  No districts exceed the 0.7 threshold. No alerts needed.\n")
        return

    print(f"\n{'='*60}")
    print(f"  ALERT: {len(high_risk)} HIGH-RISK DISTRICT(S) DETECTED")
    print(f"{'='*60}")
    for p in high_risk:
        print(f"  ⚠  {p['district']:20s}  prob={p['failure_probability']:.2f}  trend={p['trend']}")
    print(f"{'='*60}\n")

    client = anthropic.Anthropic()   # reads ANTHROPIC_API_KEY from env

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        predictions_json=json.dumps(predictions, indent=2)
    )

    user_message = (
        f"AUTOMATED ALERT: {len(high_risk)} districts have exceeded the 0.7 failure "
        f"probability threshold.\n\n"
        f"High-risk districts:\n"
        + "\n".join(
            f"• {p['district']}: {p['failure_probability']*100:.0f}% failure probability"
            for p in high_risk
        )
        + "\n\nPlease provide:\n"
          "1. A brief risk summary for each HIGH risk district\n"
          "2. Top 2 intervention actions per district\n"
          "3. Which district needs emergency attention first and why"
    )

    print("Contacting Govt Alert Agent (Claude)...\n")

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    agent_reply = response.content[0].text
    print("─── AGENT RESPONSE ─────────────────────────────────────")
    print(agent_reply)
    print("─────────────────────────────────────────────────────────\n")

    # Interactive follow-up loop
    print("You can now ask the agent follow-up questions.")
    print("Type 'exit' to quit.\n")

    conversation = [
        {"role": "user",      "content": user_message},
        {"role": "assistant", "content": agent_reply},
    ]

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("exit", "quit", "q"):
            print("Exiting agent session.")
            break
        if not user_input:
            continue

        conversation.append({"role": "user", "content": user_input})
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=conversation,
        )
        reply = response.content[0].text
        conversation.append({"role": "assistant", "content": reply})
        print(f"\nAgent: {reply}\n")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("\n" + "="*60)
    print("  DISTRICT WELFARE SCHEME FAILURE PREDICTION SYSTEM")
    print("="*60 + "\n")

    # Build dataset
    df = build_dataset()
    print(f"Dataset built: {len(df)} districts × {df.shape[1]-2} features\n")

    # Train model
    model, feature_cols = train_model(df, model_type="gradient_boosting")
    print(f"Model trained: GradientBoostingClassifier\n")

    # Feature importance
    importances = dict(zip(feature_cols, model.feature_importances_))
    print("Feature importances:")
    for feat, imp in sorted(importances.items(), key=lambda x: -x[1]):
        bar = "█" * int(imp * 40)
        print(f"  {feat:18s} {bar} {imp:.3f}")
    print()

    # Predictions
    predictions = predict_districts(model, feature_cols, df)

    # Print results table
    table_data = [
        [
            p["district"],
            f"{p['failure_probability']*100:.0f}%",
            p["risk_level"],
            f"{p['gap_ratio']:.2f}",
            f"{p['coverage_rate']:.1f}",
            f"{p['scheme_density']:.1f}",
            p["trend"],
        ]
        for p in predictions
    ]
    headers = ["District", "Fail Prob", "Risk", "Gap Ratio", "Coverage", "Scheme Density", "Trend"]
    print(tabulate(table_data, headers=headers, tablefmt="rounded_outline"))
    print()

    # Print JSON output for top HIGH risk districts
    print("JSON output (HIGH risk districts):")
    high_risk_json = [
        {
            "district":            p["district"],
            "failure_probability": p["failure_probability"],
            "risk_level":          p["risk_level"],
        }
        for p in predictions if p["risk_level"] == "HIGH"
    ]
    print(json.dumps(high_risk_json, indent=2))
    print()

    # Run alert agent
    run_alert_agent(predictions)


if __name__ == "__main__":
    main()