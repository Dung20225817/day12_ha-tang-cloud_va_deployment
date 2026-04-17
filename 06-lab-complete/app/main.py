"""Production-ready Day 12 agent with stateless Redis storage."""
import json
import logging
from pathlib import Path
import signal
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import redis
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, estimate_cost_usd, get_monthly_spending
from app.orchestrator.graph import run_graph
from app.orchestrator.knowledge_base import (
    is_using_embedded_docs,
    load_chunks,
    resolve_docs_dir,
)
from app.rate_limiter import check_rate_limit
from utils.mock_llm import ask as llm_ask

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(message)s",
)
logger = logging.getLogger(__name__)
UI_FILE = Path(__file__).resolve().parent / "ui" / "index.html"


def log_event(event: str, **fields: Any) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    logger.info(json.dumps(payload, ensure_ascii=False))


def _history_key(user_id: str) -> str:
    return f"history:{user_id}"


def _trace_key(user_id: str) -> str:
    return f"trace:{user_id}"


def load_history(rds: redis.Redis, user_id: str) -> list[dict[str, str]]:
    raw_items = rds.lrange(_history_key(user_id), -settings.history_max_messages, -1)
    history: list[dict[str, str]] = []
    for item in raw_items:
        try:
            history.append(json.loads(item))
        except json.JSONDecodeError:
            continue
    return history


def append_history(rds: redis.Redis, user_id: str, role: str, content: str) -> None:
    key = _history_key(user_id)
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    pipe = rds.pipeline(transaction=True)
    pipe.rpush(key, json.dumps(message, ensure_ascii=False))
    pipe.ltrim(key, -settings.history_max_messages, -1)
    pipe.expire(key, settings.history_ttl_seconds)
    pipe.execute()


def append_trace(rds: redis.Redis, user_id: str, trace_state: dict[str, Any]) -> None:
    key = _trace_key(user_id)
    payload = {
        "run_id": trace_state.get("run_id"),
        "route": trace_state.get("supervisor_route"),
        "route_reason": trace_state.get("route_reason"),
        "workers_called": trace_state.get("workers_called", []),
        "sources": trace_state.get("sources", []),
        "confidence": trace_state.get("confidence", 0.0),
        "latency_ms": trace_state.get("latency_ms", 0),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    pipe = rds.pipeline(transaction=True)
    pipe.rpush(key, json.dumps(payload, ensure_ascii=False))
    pipe.ltrim(key, -100, -1)
    pipe.expire(key, settings.history_ttl_seconds)
    pipe.execute()


def load_traces(rds: redis.Redis, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    safe_limit = max(1, min(limit, 100))
    raw_items = rds.lrange(_trace_key(user_id), -safe_limit, -1)
    traces: list[dict[str, Any]] = []
    for item in raw_items:
        try:
            traces.append(json.loads(item))
        except json.JSONDecodeError:
            continue
    return traces


def build_prompt(question: str, history: list[dict[str, str]]) -> str:
    if not history:
        return question
    recent_history = history[-6:]
    lines = ["Conversation context:"]
    for message in recent_history:
        role = message.get("role", "user")
        content = message.get("content", "")
        lines.append(f"{role}: {content}")
    lines.append(f"user: {question}")
    return "\n".join(lines)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.start_time = time.time()
    app.state.request_count = 0
    app.state.error_count = 0
    app.state.ready = False
    app.state.shutting_down = False

    try:
        app.state.redis = redis.from_url(settings.redis_url, decode_responses=True)
        app.state.redis.ping()
        app.state.ready = True
        chunks = load_chunks()
        sources = sorted({chunk.get("source", "unknown") for chunk in chunks})
        log_event(
            "startup",
            app=settings.app_name,
            version=settings.app_version,
            environment=settings.environment,
            redis="connected",
            kb_docs_dir=str(resolve_docs_dir()),
            kb_chunk_count=len(chunks),
            kb_source_count=len(sources),
            kb_using_embedded_docs=is_using_embedded_docs(),
        )
    except redis.RedisError as exc:
        app.state.redis = None
        log_event("startup_failed", reason="redis_unavailable", detail=str(exc))

    yield

    app.state.ready = False
    if app.state.redis is not None:
        try:
            app.state.redis.close()
        except Exception:
            pass
    log_event("shutdown")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)


def _handle_sigterm(signum, _frame):
    app.state.shutting_down = True
    log_event("signal", signum=signum, action="graceful_shutdown")


signal.signal(signal.SIGTERM, _handle_sigterm)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    app.state.request_count += 1
    start = time.time()

    if app.state.shutting_down and request.url.path not in {"/health", "/ready"}:
        return Response(
            status_code=503,
            media_type="application/json",
            content=json.dumps({"detail": "Server is shutting down"}),
        )

    try:
        response: Response = await call_next(request)
    except Exception as exc:
        app.state.error_count += 1
        log_event("request_error", path=request.url.path, error=str(exc))
        raise

    duration_ms = round((time.time() - start) * 1000, 2)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    if "server" in response.headers:
        del response.headers["server"]
    log_event(
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration_ms,
    )
    return response


class AskRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)
    question: str = Field(..., min_length=1, max_length=2000)


class AskResponse(BaseModel):
    user_id: str
    question: str
    answer: str
    model: str
    route: str
    route_reason: str
    workers_called: list[str]
    sources: list[str]
    confidence: float
    run_id: str
    latency_ms: int
    history_items: int
    monthly_spending_usd: float
    monthly_budget_usd: float
    timestamp: str


class TraceResponse(BaseModel):
    user_id: str
    total: int
    traces: list[dict[str, Any]]


@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "endpoints": {
            "ui": "GET /ui",
            "ask": "POST /ask",
            "health": "GET /health",
            "ready": "GET /ready",
            "trace": "GET /trace/{user_id}",
            "kb_status": "GET /kb-status",
        },
    }


@app.get("/ui", response_class=HTMLResponse, tags=["Info"])
def ui_page():
    if not UI_FILE.exists():
        return HTMLResponse(
            "<h1>UI not found</h1><p>Create app/ui/index.html first.</p>",
            status_code=404,
        )
    return HTMLResponse(UI_FILE.read_text(encoding="utf-8"))


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(body: AskRequest, _api_key: str = Depends(verify_api_key)):
    if app.state.redis is None:
        raise HTTPException(status_code=503, detail="Redis unavailable")

    check_rate_limit(body.user_id, app.state.redis)

    history = load_history(app.state.redis, body.user_id)
    history_lines = [
        f"{item.get('role', 'user')}: {item.get('content', '')}"
        for item in history[-6:]
    ]

    orchestration_state = run_graph(body.question, history_lines)
    answer = (orchestration_state.get("final_answer") or "").strip()

    # Fallback for unexpected empty synthesis output.
    if not answer:
        prompt = build_prompt(body.question, history)
        answer = llm_ask(prompt)
        orchestration_state["final_answer"] = answer
        orchestration_state.setdefault("supervisor_route", "retrieval_worker")
        orchestration_state.setdefault("route_reason", "fallback to mock_llm due to empty synthesis")
        orchestration_state.setdefault("workers_called", ["fallback_llm"])
        orchestration_state.setdefault("sources", [])
        orchestration_state.setdefault("confidence", 0.3)
        orchestration_state.setdefault("run_id", "fallback-run")
        orchestration_state.setdefault("latency_ms", 0)

    estimated_cost = estimate_cost_usd(body.question, answer)
    check_budget(body.user_id, estimated_cost, app.state.redis)

    append_history(app.state.redis, body.user_id, "user", body.question)
    append_history(app.state.redis, body.user_id, "assistant", answer)
    append_trace(app.state.redis, body.user_id, orchestration_state)
    updated_history = load_history(app.state.redis, body.user_id)
    spending = get_monthly_spending(body.user_id, app.state.redis)

    return AskResponse(
        user_id=body.user_id,
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        route=orchestration_state.get("supervisor_route", "retrieval_worker"),
        route_reason=orchestration_state.get("route_reason", "unknown"),
        workers_called=orchestration_state.get("workers_called", []),
        sources=orchestration_state.get("sources", []),
        confidence=float(orchestration_state.get("confidence", 0.0) or 0.0),
        run_id=orchestration_state.get("run_id", "unknown"),
        latency_ms=int(orchestration_state.get("latency_ms", 0) or 0),
        history_items=len(updated_history),
        monthly_spending_usd=spending,
        monthly_budget_usd=settings.monthly_budget_usd,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/health", tags=["Operations"])
def health():
    redis_ok = False
    if app.state.redis is not None:
        try:
            app.state.redis.ping()
            redis_ok = True
        except redis.RedisError:
            redis_ok = False

    uptime = round(time.time() - app.state.start_time, 2)
    status = "ok" if redis_ok else "degraded"
    return {
        "status": status,
        "uptime_seconds": uptime,
        "version": settings.app_version,
        "environment": settings.environment,
        "redis_connected": redis_ok,
        "total_requests": app.state.request_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready():
    if not app.state.ready or app.state.redis is None or app.state.shutting_down:
        raise HTTPException(status_code=503, detail="Not ready")
    try:
        app.state.redis.ping()
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    return {"ready": True}


@app.get("/metrics", tags=["Operations"])
def metrics(_api_key: str = Depends(verify_api_key)):
    uptime = round(time.time() - app.state.start_time, 2)
    return {
        "uptime_seconds": uptime,
        "total_requests": app.state.request_count,
        "error_count": app.state.error_count,
        "rate_limit_per_minute": settings.rate_limit_per_minute,
        "monthly_budget_usd": settings.monthly_budget_usd,
    }


@app.get("/kb-status", tags=["Operations"])
def kb_status(_api_key: str = Depends(verify_api_key)):
    chunks = load_chunks()
    sources = sorted({chunk.get("source", "unknown") for chunk in chunks})
    return {
        "docs_dir": str(resolve_docs_dir()),
        "using_embedded_docs": is_using_embedded_docs(),
        "chunk_count": len(chunks),
        "source_count": len(sources),
        "sources": sources,
    }


@app.get("/trace/{user_id}", response_model=TraceResponse, tags=["Operations"])
def get_user_traces(
    user_id: str,
    limit: int = 20,
    _api_key: str = Depends(verify_api_key),
):
    if app.state.redis is None:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    traces = load_traces(app.state.redis, user_id, limit)
    return TraceResponse(user_id=user_id, total=len(traces), traces=traces)


if __name__ == "__main__":
    log_event("boot", host=settings.host, port=settings.port)
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
