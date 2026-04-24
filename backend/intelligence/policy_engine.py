"""
NPIDE - Policy efficiency engine and spike detector.
"""

import time

from sqlalchemy import text

from backend.data_layer.cache import cache_get, cache_get_raw, cache_incr, cache_set, cache_set_raw
from backend.data_layer.database import engine
from backend.data_layer.queries import get_dashboard_stats, get_gap_detection, get_policy_leaderboard, get_zero_application_schemes


def get_scheme_efficiency(scheme_id: int) -> dict:
    cache_key = f"eff:scheme:{scheme_id}"
    cached = cache_get(cache_key)
    if cached:
        return {**cached, "source": "cache"}

    sql = text("""
        SELECT
            s.scheme_name,
            pa.total_eligible,
            pa.total_applied,
            pa.total_approved,
            pa.efficiency_score,
            (pa.total_eligible - pa.total_applied) AS gap_count,
            pa.computed_at
        FROM policy_analytics pa
        JOIN schemes s ON s.scheme_id = pa.scheme_id
        WHERE pa.scheme_id = :sid
        LIMIT 1
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"sid": scheme_id}).mappings().fetchone()

    if not row:
        return {"error": f"No analytics data for scheme_id={scheme_id}"}

    data = dict(row)
    efficiency = float(data.get("efficiency_score") or 0)
    result = {
        **data,
        "efficiency_score": efficiency,
        "rating": (
            "excellent" if efficiency >= 90 else
            "good" if efficiency >= 70 else
            "fair" if efficiency >= 50 else
            "poor" if efficiency >= 30 else
            "critical"
        ),
        "computed_at": str(data.get("computed_at", "")),
        "source": "computed",
    }
    cache_set(cache_key, result, ttl_seconds=300)
    return result


def get_efficiency_leaderboard() -> dict:
    cache_key = "eff:leaderboard"
    cached = cache_get(cache_key)
    if cached:
        return {**cached, "source": "cache"}

    leaderboard = get_policy_leaderboard()
    zero_schemes = get_zero_application_schemes()
    stats = get_dashboard_stats()

    result = {
        "leaderboard": leaderboard,
        "zero_schemes": zero_schemes,
        "summary": {
            "total_schemes": stats.get("active_schemes", 0),
            "avg_efficiency": float(stats.get("avg_efficiency") or 0),
            "open_grievances": stats.get("open_grievances", 0),
            "total_applications": stats.get("total_applications", 0),
            "approved_count": stats.get("approved_count", 0),
        },
        "computed_at": time.time(),
        "source": "computed",
    }
    cache_set(cache_key, result, ttl_seconds=300)
    return result


def get_admin_dashboard() -> dict:
    cache_key = "admin:dashboard"
    cached = cache_get(cache_key)
    if cached:
        return {**cached, "source": "cache"}

    stats = get_dashboard_stats()
    leaderboard = get_policy_leaderboard()
    gaps = get_gap_detection()

    result = {
        "stats": stats,
        "leaderboard": leaderboard[:10],
        "top_gaps": gaps[:10],
        "computed_at": time.time(),
        "source": "computed",
    }
    cache_set(cache_key, result, ttl_seconds=120)
    return result


EWMA_ALPHA = 0.3
SPIKE_THRESH = 2.5


def record_and_detect_spike(location: str, category: str) -> dict:
    bucket_key = f"complaints:{location}:{category}:5min"
    ewma_key = f"ewma:{location}:{category}"

    current_count = cache_incr(bucket_key, ttl_seconds=300)
    prev_str = cache_get_raw(ewma_key)
    prev_ewma = float(prev_str) if prev_str else float(current_count)
    new_ewma = EWMA_ALPHA * current_count + (1 - EWMA_ALPHA) * prev_ewma
    cache_set_raw(ewma_key, str(round(new_ewma, 4)), ttl_seconds=3600)

    threshold = SPIKE_THRESH * max(prev_ewma, 1)
    is_spike = (current_count > threshold) and (current_count - 1 <= threshold)
    return {
        "location": location,
        "category": category,
        "current_5min": current_count,
        "ewma_baseline": round(prev_ewma, 2),
        "is_spike": is_spike,
        "alert": f"SPIKE: {category} complaints surging in {location}!" if is_spike else None,
    }


def get_active_spikes() -> list[dict]:
    try:
        from backend.data_layer.cache import REDIS

        spike_keys = list(REDIS.scan_iter("complaints:*:5min"))
        spikes = []
        for key in spike_keys[:50]:
            parts = key.split(":")
            if len(parts) >= 4:
                location = parts[1]
                category = parts[2]
                count = int(REDIS.get(key) or 0)
                ewma_str = REDIS.get(f"ewma:{location}:{category}")
                ewma = float(ewma_str) if ewma_str else count
                if count > SPIKE_THRESH * max(ewma, 1):
                    spikes.append({
                        "location": location,
                        "category": category,
                        "current": count,
                        "baseline": round(ewma, 2),
                    })
        return spikes
    except Exception:
        return []
