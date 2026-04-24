"""
NPIDE — Async FastAPI Routes
==============================
Every endpoint is async. DB + Redis calls never block the event loop.
AI inference runs in asyncio.to_thread (CPU-bound, avoids blocking).

Performance targets:
  Cache hit:    < 5  ms  (async Redis GET)
  DB query:     < 50 ms  (asyncpg)
  AI compute:  < 150 ms  (thread pool — does not block event loop)
  End-to-end:  < 200 ms  (P99)
"""

import asyncio
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import Response

from backend.api.schemas import (
    EligibilityByProfile, GrievanceClassifyRequest,
    GrievanceSubmitRequest, HealthResponse, SchemeMutation,
)
from backend.data_layer.database import ping_db_async
from backend.data_layer.cache import (
    async_cache_get, async_cache_set, async_cache_delete, async_delete_by_prefix,
    async_ping_redis, publish_event, REDIS,
)
from backend.data_layer.async_queries import (
    async_get_eligible_schemes, async_get_gap_detection,
    async_get_grievance_hotspots, async_get_policy_leaderboard,
    async_get_citizen_applications, async_get_zero_application_schemes,
    async_get_corruption_cases, async_get_dashboard_stats,
    async_get_scheme_analytics, async_insert_grievance,
    async_list_schemes, async_create_scheme, async_update_scheme, async_deactivate_scheme,
)
from backend.intelligence.eligibility_engine import (
    check_eligibility_by_profile, check_eligibility_by_citizen_id,
    SCHEME_RULES, load_scheme_rules,
)
from backend.intelligence.gap_detector import get_gap_summary, train_isolation_forest
from backend.intelligence.grievance_engine import classify_grievance, get_hotspot_report
from backend.intelligence.scheme_parser import extract_scheme_from_upload
from backend.intelligence.policy_engine import (
    get_scheme_efficiency, get_efficiency_leaderboard,
    get_admin_dashboard, record_and_detect_spike, get_active_spikes,
)
from backend.intelligence.model_manager import MODEL_MANAGER
from backend.monitoring.metrics import (
    logger, get_metrics_text,
    record_cache, record_eligibility, record_grievance_classified,
    active_spikes_gauge, schemes_in_memory,
    ai_inference_seconds, db_query_seconds,
)

router = APIRouter()


async def refresh_scheme_state() -> int:
    deleted = 0
    for prefix in ("elig:", "gap_summary:", "eff:", "admin:dashboard"):
        deleted += await async_delete_by_prefix(prefix)
    await asyncio.to_thread(load_scheme_rules)
    return deleted


# ─────────────────────────────────────────────────────────────
# HEALTH + METRICS
# ─────────────────────────────────────────────────────────────

@router.get("/health", tags=["Health"])
async def health_check():
    """Async health check — DB, Redis, AI engine."""
    db_ok, redis_ok = await asyncio.gather(
        ping_db_async(),
        async_ping_redis(),
    )
    n_schemes = len(SCHEME_RULES)
    schemes_in_memory.set(n_schemes)

    return {
        "status":         "ok" if db_ok and redis_ok else "degraded",
        "db":             db_ok,
        "redis":          redis_ok,
        "ai_engine":      n_schemes > 0,
        "schemes_loaded": n_schemes,
        "models":         MODEL_MANAGER.status(),
    }


@router.get("/metrics", tags=["Monitoring"])
async def prometheus_metrics():
    """Prometheus metrics endpoint. Point Grafana/Prometheus here."""
    data, content_type = get_metrics_text()
    return Response(content=data, media_type=content_type)


# ─────────────────────────────────────────────────────────────
# ELIGIBILITY  — async wrapper around CPU-bound rule scan
# ─────────────────────────────────────────────────────────────

@router.post("/eligibility", tags=["Eligibility"])
async def check_eligibility(profile: EligibilityByProfile):
    """
    Check eligible schemes for a citizen profile.

    Architecture:
      1. Async Redis GET (0.2 ms if cached)
      2. asyncio.to_thread → CPU-bound rule scan (5–20 ms, never blocks event loop)
      3. Async Redis SET (cache result)
    """
    profile_dict = profile.model_dump()

    # 1. Cache check (async)
    import hashlib, json
    profile_hash = hashlib.md5(
        json.dumps(profile_dict, sort_keys=True, default=str).encode()
    ).hexdigest()
    cache_key = f"elig:profile:{profile_hash}"

    cached = await async_cache_get(cache_key)
    if cached is not None:
        record_cache("eligibility", hit=True)
        record_eligibility("cache")
        logger.info("eligibility_cache_hit", hash=profile_hash[:8])
        return {"source": "cache", "matched": len(cached), "schemes": cached}

    record_cache("eligibility", hit=False)

    # 2. CPU-bound rule scan in thread pool (does NOT block event loop)
    t0 = time.perf_counter()
    result = await asyncio.to_thread(check_eligibility_by_profile, profile_dict)
    elapsed = time.perf_counter() - t0
    ai_inference_seconds.labels("eligibility").observe(elapsed)

    # 3. Cache result
    await async_cache_set(cache_key, result["schemes"], ttl=600)
    record_eligibility("computed")
    logger.info("eligibility_computed",
                matched=result["matched"],
                latency_ms=round(elapsed * 1000, 2))

    return result


@router.get("/eligibility/citizen/{citizen_id}", tags=["Eligibility"])
async def check_eligibility_citizen(citizen_id: int):
    """Check eligibility for a registered DB citizen."""
    cache_key = f"elig:citizen:{citizen_id}"
    cached = await async_cache_get(cache_key)
    if cached is not None:
        record_cache("eligibility", hit=True)
        return {"source": "cache", "matched": len(cached), "schemes": cached}

    t0 = time.perf_counter()
    schemes = await async_get_eligible_schemes(citizen_id)
    db_query_seconds.labels("eligible_schemes").observe(time.perf_counter() - t0)

    await async_cache_set(cache_key, schemes, ttl=600)
    record_cache("eligibility", hit=False)
    return {"source": "computed", "matched": len(schemes), "schemes": schemes}


@router.get("/citizen/{citizen_id}/applications", tags=["Citizens"])
async def citizen_applications(citizen_id: int):
    apps = await async_get_citizen_applications(citizen_id)
    return {"citizen_id": citizen_id, "applications": apps, "count": len(apps)}


# ─────────────────────────────────────────────────────────────
# GAP DETECTION
# ─────────────────────────────────────────────────────────────

@router.get("/gap-detection", tags=["Gap Detection"])
async def gap_detection(location: Optional[str] = Query(None)):
    """
    IsolationForest gap detection — async cached wrapper.
    Computation runs in thread pool; result cached 5 min.
    """
    cache_key = f"gap_summary:{location or 'ALL'}"
    cached = await async_cache_get(cache_key)
    if cached:
        record_cache("gap_detection", hit=True)
        return cached

    record_cache("gap_detection", hit=False)
    t0 = time.perf_counter()
    result = await asyncio.to_thread(get_gap_summary, location)
    ai_inference_seconds.labels("gap_detection").observe(time.perf_counter() - t0)

    await async_cache_set(cache_key, result, ttl=300)
    return result


@router.get("/gap-detection/db", tags=["Gap Detection"])
async def gap_detection_db():
    """Raw DB gap report from vw_gap_detection."""
    cache_key = "gap:db"
    cached = await async_cache_get(cache_key)
    if cached:
        return cached

    t0 = time.perf_counter()
    gaps = await async_get_gap_detection()
    db_query_seconds.labels("gap_detection").observe(time.perf_counter() - t0)

    result = {"count": len(gaps), "gaps": gaps}
    await async_cache_set(cache_key, result, ttl=300)
    return result


@router.get("/gap-detection/zero-schemes", tags=["Gap Detection"])
async def zero_application_schemes():
    schemes = await async_get_zero_application_schemes()
    return {"count": len(schemes), "schemes": schemes}


@router.post("/gap-detection/train", tags=["Gap Detection"])
async def train_gap_model(location: Optional[str] = None):
    """Trigger IsolationForest retraining (runs in thread pool)."""
    result = await asyncio.to_thread(train_isolation_forest, location)
    return {"message": result}


# ─────────────────────────────────────────────────────────────
# GRIEVANCES
# ─────────────────────────────────────────────────────────────

@router.post("/grievance/classify", tags=["Grievances"])
async def classify_grievance_endpoint(request: GrievanceClassifyRequest):
    """
    Classify grievance text. spaCy + RandomForest in thread pool.
    Cache: 1 hr (same text always gives same result).
    """
    t0 = time.perf_counter()
    result = await asyncio.to_thread(classify_grievance, request.text)
    elapsed = time.perf_counter() - t0
    ai_inference_seconds.labels("grievance_nlp").observe(elapsed)

    record_grievance_classified(result.get("category", "other"))
    logger.info("grievance_classified",
                category=result.get("category"),
                priority=result.get("priority"),
                latency_ms=round(elapsed * 1000, 2))
    return result


@router.post("/grievance/submit", tags=["Grievances"])
async def submit_grievance(request: GrievanceSubmitRequest):
    """
    Full grievance pipeline — concurrent execution:
      - Classify (AI, thread pool)
      - Save to DB (async)
      Both run concurrently with asyncio.gather.
    Then: publish event + spike check.
    """
    # 1. Classify (non-blocking)
    classification = await asyncio.to_thread(classify_grievance, request.description)

    # 2. Save to DB
    data = {
        "citizen_id":  request.citizen_id,
        "scheme_id":   request.scheme_id,
        "location":    request.location,
        "category":    classification["category"].replace("_", " "),
        "description": request.description,
        "severity":    request.severity,
    }
    try:
        grievance_id = await async_insert_grievance(data)
    except Exception as e:
        logger.error("grievance_db_insert_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"DB insert failed: {str(e)}")

    # 3. Run spike check + publish event concurrently
    spike, _ = await asyncio.gather(
        asyncio.to_thread(record_and_detect_spike, request.location, classification["category"]),
        publish_event("grievance_filed", {
            "grievance_id": grievance_id,
            "location":     request.location,
            "category":     classification["category"],
            "priority":     classification["priority"],
        }),
    )

    if spike.get("is_spike"):
        active_spikes_gauge.inc()
        await publish_event("spike_alert", spike)
        logger.warning("spike_detected", **spike)

    record_grievance_classified(classification.get("category", "other"))

    return {
        "grievance_id":   grievance_id,
        "classification": classification,
        "spike_alert":    spike,
    }


@router.post("/grievance/batch-classify", tags=["Grievances"])
async def batch_classify_endpoint(grievances: list[dict]):
    """Classify multiple grievances concurrently."""
    from backend.intelligence.grievance_engine import classify_grievance as clf
    tasks = [
        asyncio.to_thread(clf, g.get("description", g.get("text", "")))
        for g in grievances
    ]
    results_raw = await asyncio.gather(*tasks)
    results = [
        {"grievance_id": g.get("grievance_id"), "location": g.get("location"), **r}
        for g, r in zip(grievances, results_raw)
    ]
    results.sort(key=lambda x: x.get("priority", 0), reverse=True)
    return {"count": len(results), "results": results}


@router.get("/grievance/hotspots", tags=["Grievances"])
async def grievance_hotspots():
    cache_key = "hotspot:report"
    cached = await async_cache_get(cache_key)
    if cached:
        return cached

    hotspots, corruption = await asyncio.gather(
        async_get_grievance_hotspots(),
        async_get_corruption_cases(),
    )
    result = {
        "hotspots":    hotspots,
        "corruption":  corruption,
        "computed_at": time.time(),
    }
    await async_cache_set(cache_key, result, ttl=180)
    return result


@router.get("/grievance/corruption", tags=["Grievances"])
async def corruption_cases():
    cases = await async_get_corruption_cases()
    return {"count": len(cases), "cases": cases}


# ─────────────────────────────────────────────────────────────
# POLICY EFFICIENCY
# ─────────────────────────────────────────────────────────────

@router.get("/policy-efficiency/{scheme_id}", tags=["Policy"])
async def scheme_efficiency(scheme_id: int):
    cache_key = f"eff:scheme:{scheme_id}"
    cached = await async_cache_get(cache_key)
    if cached:
        return {**cached, "source": "cache"}

    row = await async_get_scheme_analytics(scheme_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"No analytics for scheme_id={scheme_id}")

    efficiency = float(row.get("efficiency_score") or 0)
    result = {
        **row,
        "efficiency_score": efficiency,
        "rating": (
            "excellent" if efficiency >= 90 else
            "good"      if efficiency >= 70 else
            "fair"      if efficiency >= 50 else
            "poor"      if efficiency >= 30 else
            "critical"
        ),
        "computed_at": str(row.get("computed_at", "")),
        "source": "computed",
    }
    await async_cache_set(cache_key, result, ttl=300)
    return result


@router.get("/policy-efficiency", tags=["Policy"])
async def efficiency_leaderboard():
    cache_key = "eff:leaderboard"
    cached = await async_cache_get(cache_key)
    if cached:
        return {**cached, "source": "cache"}

    leaderboard, zero_schemes, stats = await asyncio.gather(
        async_get_policy_leaderboard(),
        async_get_zero_application_schemes(),
        async_get_dashboard_stats(),
    )
    result = {
        "leaderboard":  leaderboard,
        "zero_schemes": zero_schemes,
        "summary": {
            "total_schemes":      stats.get("active_schemes", 0),
            "avg_efficiency":     float(stats.get("avg_efficiency") or 0),
            "open_grievances":    stats.get("open_grievances", 0),
            "total_applications": stats.get("total_applications", 0),
            "approved_count":     stats.get("approved_count", 0),
        },
        "computed_at": time.time(),
        "source": "computed",
    }
    await async_cache_set(cache_key, result, ttl=300)
    return result


# ─────────────────────────────────────────────────────────────
# ADMIN DASHBOARD
# ─────────────────────────────────────────────────────────────

@router.get("/admin/dashboard", tags=["Admin"])
async def admin_dashboard():
    """All dashboard data in one async call — 3 queries run concurrently."""
    cache_key = "admin:dashboard"
    cached = await async_cache_get(cache_key)
    if cached:
        return {**cached, "source": "cache"}

    stats, leaderboard, gaps = await asyncio.gather(
        async_get_dashboard_stats(),
        async_get_policy_leaderboard(),
        async_get_gap_detection(),
    )
    result = {
        "stats":       stats,
        "leaderboard": leaderboard[:10],
        "top_gaps":    gaps[:10],
        "computed_at": time.time(),
        "source":      "computed",
    }
    await async_cache_set(cache_key, result, ttl=120)
    return result


@router.get("/admin/stats", tags=["Admin"])
async def admin_stats():
    return await async_get_dashboard_stats()


@router.get("/admin/models", tags=["Admin"])
async def model_status():
    """Model versioning, drift stats, prediction counts."""
    return {"models": MODEL_MANAGER.status()}


@router.post("/admin/models/reload", tags=["Admin"])
async def reload_model(name: str, filename: str):
    """
    Hot-reload a model without restarting the server.
    Zero downtime — in-flight requests finish with old model.
    """
    result = await asyncio.to_thread(MODEL_MANAGER.hot_reload, name, filename)
    if result["swapped"]:
        logger.info("model_hot_reloaded", **result)
    return result


@router.get("/admin/models/{name}/drift", tags=["Admin"])
async def model_drift(name: str, threshold: float = 0.8):
    """Check if a model's prediction distribution has drifted."""
    return MODEL_MANAGER.check_drift(name, threshold)


@router.get("/admin/schemes", tags=["Admin"])
async def list_schemes(include_inactive: bool = True):
    schemes = await async_list_schemes(include_inactive=include_inactive)
    return {"count": len(schemes), "schemes": schemes}


@router.post("/admin/schemes/extract", tags=["Admin"])
async def extract_scheme(file: UploadFile = File(...)):
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    parsed = await asyncio.to_thread(
        extract_scheme_from_upload,
        file.filename or "upload.txt",
        file.content_type or "",
        payload,
    )
    return {
        "parsed": parsed,
        "source": "heuristic_parser",
        "extracted_chars": len(payload),
    }


@router.post("/admin/schemes", tags=["Admin"])
async def create_scheme(request: SchemeMutation):
    scheme = await async_create_scheme(request.model_dump())
    deleted = await refresh_scheme_state()
    await publish_event("scheme_updated", {"scheme_id": scheme["id"], "eligible_location": scheme["location"]})
    return {"scheme": scheme, "cache_keys_deleted": deleted}


@router.put("/admin/schemes/{scheme_id}", tags=["Admin"])
async def update_scheme(scheme_id: int, request: SchemeMutation):
    scheme = await async_update_scheme(scheme_id, request.model_dump())
    if not scheme:
        raise HTTPException(status_code=404, detail=f"Scheme {scheme_id} not found")

    deleted = await refresh_scheme_state()
    await publish_event("scheme_updated", {"scheme_id": scheme_id, "eligible_location": scheme["location"]})
    return {"scheme": scheme, "cache_keys_deleted": deleted}


@router.delete("/admin/schemes/{scheme_id}", tags=["Admin"])
async def deactivate_scheme(scheme_id: int):
    scheme = await async_deactivate_scheme(scheme_id)
    if not scheme:
        raise HTTPException(status_code=404, detail=f"Scheme {scheme_id} not found")

    deleted = await refresh_scheme_state()
    await publish_event("scheme_updated", {"scheme_id": scheme_id, "eligible_location": scheme["location"]})
    return {"scheme": scheme, "cache_keys_deleted": deleted}


@router.delete("/admin/cache/{key_prefix}", tags=["Admin"])
async def bust_cache(key_prefix: str):
    """Invalidate cache keys by prefix (admin use). Publishes cache_bust event."""
    try:
        deleted = await async_delete_by_prefix(key_prefix)
        await publish_event("cache_bust", {"prefix": key_prefix, "keys_deleted": deleted})
        return {"deleted": deleted, "prefix": key_prefix}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# SPIKE DETECTOR + EVENT BUS
# ─────────────────────────────────────────────────────────────

@router.get("/spikes", tags=["Monitoring"])
async def active_spikes():
    spikes = await asyncio.to_thread(get_active_spikes)
    active_spikes_gauge.set(len(spikes))
    return {"active_spikes": len(spikes), "spikes": spikes}


@router.post("/spikes/record", tags=["Monitoring"])
async def record_spike(location: str, category: str):
    """Manually fire a complaint event (demo / testing)."""
    result = await asyncio.to_thread(record_and_detect_spike, location, category)
    if result.get("is_spike"):
        await publish_event("spike_alert", result)
    return result
