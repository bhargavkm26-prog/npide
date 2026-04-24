"""
NPIDE — Eligibility Engine
============================
Rule-based scheme matching. Zero ML, zero LLM.

Why rule-based?
  Government schemes have EXACT eligibility criteria — income < 2.5L,
  age 18–60, gender = Female, state = Karnataka. Rules are interpretable,
  auditable, and cannot hallucinate.

Hot path (cache hit):  1 Redis GET  ≈ 0.2 ms
Cold path (first):     scan all schemes in memory → cache result

Connects to real data via:
  - SCHEME_RULES loaded from DB at startup (load_scheme_rules)
  - Direct profile-based matching for profile dicts (no citizen_id needed)
  - Citizen-ID-based matching using DB query (get_eligible_schemes)
"""

import json
import hashlib
from typing import Optional

from backend.data_layer.cache import cache_get, cache_set
from backend.data_layer.queries import load_all_active_schemes, get_eligible_schemes


# ── In-memory scheme store (loaded once at startup) ──────────
SCHEME_RULES: list[dict] = []


def load_scheme_rules() -> None:
    """
    Pull ALL active scheme rules once and cache in memory.
    Called once at app startup. Re-call when schemes are updated.
    Average size: 10–5000 schemes × ~200 bytes = negligible RAM.
    """
    global SCHEME_RULES
    SCHEME_RULES = load_all_active_schemes()
    print(f"[ELIGIBILITY] Loaded {len(SCHEME_RULES)} active schemes into memory.")


# ── Core rule evaluator ───────────────────────────────────────

def _evaluate_scheme(scheme: dict, profile: dict) -> bool:
    """
    Pure rule evaluation — O(1) per scheme, no I/O.
    Profile keys: income, age, gender, location, occupation
    Scheme columns map directly from DB.
    """
    income     = profile.get("income", 0)
    age        = profile.get("age", 0)
    gender     = profile.get("gender", "")
    location   = profile.get("location", "")
    occupation = profile.get("occupation", "")

    if not (scheme["min_income"] <= income <= scheme["max_income"]):
        return False
    if not (scheme["min_age"] <= age <= scheme["max_age"]):
        return False
    if scheme["eligible_gender"] != "All" and scheme["eligible_gender"] != gender:
        return False
    if scheme["eligible_location"] != "All" and scheme["eligible_location"] != location:
        return False
    if scheme["eligible_occupation"] != "All" and scheme["eligible_occupation"] != occupation:
        return False
    return True


# ── Public API ────────────────────────────────────────────────

def check_eligibility_by_profile(profile: dict) -> dict:
    """
    Check eligibility from a raw profile dict (from chatbot onboarding).
    Profile must have: income, age, gender, location, occupation.

    Hot path  → Redis cache
    Cold path → scan SCHEME_RULES in memory
    Returns list of matching schemes with name, description, benefit.
    """
    # Normalise income_range → income if needed (from chatbot)
    if "income_range" in profile and "income" not in profile:
        income_map = {
            "Below ₹1 Lakh": 80000,
            "₹1L – ₹2.5L": 175000,
            "₹2.5L – ₹5L": 375000,
            "₹5L – ₹8L": 650000,
            "Above ₹8L": 900000,
        }
        profile = {**profile, "income": income_map.get(profile["income_range"], 300000)}

    # Stable hash of profile for caching
    profile_hash = hashlib.md5(
        json.dumps(profile, sort_keys=True, default=str).encode()
    ).hexdigest()
    cache_key = f"elig:profile:{profile_hash}"

    cached = cache_get(cache_key)
    if cached is not None:
        return {"source": "cache", "matched": len(cached), "schemes": cached}

    # Cold scan
    if not SCHEME_RULES:
        load_scheme_rules()

    eligible = [
        {
            "scheme_id":    s["scheme_id"],
            "scheme_name":  s["scheme_name"],
            "description":  s["description"],
            "benefit_amount": s["benefit_amount"],
            "eligible_location": s["eligible_location"],
        }
        for s in SCHEME_RULES
        if _evaluate_scheme(s, profile)
    ]

    cache_set(cache_key, eligible, ttl_seconds=600)  # 10 min TTL
    return {"source": "computed", "matched": len(eligible), "schemes": eligible}


def check_eligibility_by_citizen_id(citizen_id: int) -> dict:
    """
    Check eligibility for a known citizen in the DB.
    Uses the optimised SQL query (key_queries.sql Query 1).
    Cached for 10 minutes.
    """
    cache_key = f"elig:citizen:{citizen_id}"
    cached = cache_get(cache_key)
    if cached is not None:
        return {"source": "cache", "matched": len(cached), "schemes": cached}

    schemes = get_eligible_schemes(citizen_id)
    cache_set(cache_key, schemes, ttl_seconds=600)
    return {"source": "computed", "matched": len(schemes), "schemes": schemes}
