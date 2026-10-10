import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.rate_limit import RateLimitMiddleware, close_redis, get_redis
from app.db.session import engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await close_redis()
    await engine.dispose()


app = FastAPI(title="Pinstagram API", version="1.0.0", lifespan=lifespan)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(v1_router, prefix="/api/v1")


@app.exception_handler(IntegrityError)
async def integrity_error_handler(_request: Request, _exc: IntegrityError):
    # Unique/foreign-key violations that slipped past service-level checks
    # (usually a race between two concurrent requests).
    return JSONResponse(status_code=409, content={"detail": "Conflict"})


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    checks = {}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
    try:
        await get_redis().ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"
    ok = all(v == "ok" for v in checks.values())
    return JSONResponse(status_code=200 if ok else 503, content=checks)
