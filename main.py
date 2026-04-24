"""
NPIDE - FastAPI application entrypoint.
"""

import asyncio
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    t0 = time.perf_counter()
    print("[NPIDE] Starting up...")

    try:
        from backend.intelligence.eligibility_engine import load_scheme_rules
        load_scheme_rules()
    except Exception as e:
        print(f"[NPIDE] Scheme rules: {e}")

    try:
        from backend.intelligence.model_manager import load_all_models
        results = load_all_models()
        print(f"[NPIDE] Models: {results}")
    except Exception as e:
        print(f"[NPIDE] Model loading: {e}")

    try:
        from backend.data_layer.cache import async_ping_redis
        from backend.data_layer.database import ping_db_async

        db_ok, redis_ok = await asyncio.gather(ping_db_async(), async_ping_redis())
        print(f"[NPIDE] DB: {'OK' if db_ok else 'FAIL'}  Redis: {'OK' if redis_ok else 'FAIL'}")
    except Exception as e:
        print(f"[NPIDE] Health check: {e}")

    elapsed = (time.perf_counter() - t0) * 1000
    print(f"[NPIDE] Ready in {elapsed:.0f}ms - http://localhost:8000/docs")
    yield

    print("[NPIDE] Shutting down.")
    try:
        from backend.data_layer.database import async_engine
        await async_engine.dispose()
    except Exception:
        pass


app = FastAPI(
    title="NPIDE - National Policy Intelligence & Delivery Engine",
    description="""
## Architecture

Async FastAPI with local DB/cache fallbacks.

- Eligibility: rule-based
- Gap detection: IsolationForest
- Grievance NLP: keyword or model-based
- Spike detection: EWMA
- Monitoring: Prometheus metrics and structured logs
    """,
    version="2.0.0",
    lifespan=lifespan,
)

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist"
FRONTEND_ASSETS_DIR = FRONTEND_DIST_DIR / "assets"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    from backend.monitoring.metrics import track_request
    return await track_request(request, call_next)


from backend.api.routes import router

app.include_router(router, prefix="/api/v1")

if FRONTEND_ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_ASSETS_DIR), name="frontend-assets")


def frontend_available() -> bool:
    return FRONTEND_DIST_DIR.joinpath("index.html").exists()


@app.get("/")
async def root():
    if frontend_available():
        return FileResponse(FRONTEND_DIST_DIR / "index.html")

    return {
        "project": "NPIDE",
        "version": "2.0.0",
        "docs": "/docs",
        "metrics": "/api/v1/metrics",
        "health": "/api/v1/health",
        "architecture": "async FastAPI + SQLite fallback + memory cache + IsolationForest + grievance classifier",
    }


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if not frontend_available():
        raise HTTPException(status_code=404, detail="Frontend build not found")

    target = FRONTEND_DIST_DIR / full_path
    if full_path and target.is_file():
        return FileResponse(target)

    return FileResponse(FRONTEND_DIST_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("APP_PORT", 8000)), reload=False)
