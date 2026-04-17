"""Retrieval worker for supervisor-worker pipeline."""
from __future__ import annotations

from app.orchestrator.knowledge_base import search_kb

WORKER_NAME = "retrieval_worker"


def run(state: dict) -> dict:
    task = (state.get("task") or "").strip()
    top_k = state.get("retrieval_top_k", 5)

    try:
        top_k = max(1, int(top_k))
    except (TypeError, ValueError):
        top_k = 5

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state.setdefault("worker_io_logs", [])

    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {"task": task, "top_k": top_k},
        "output": None,
        "error": None,
    }

    if not task:
        state["retrieved_chunks"] = []
        state["retrieved_sources"] = []
        worker_io["output"] = {"chunks_count": 0, "sources": []}
        state["history"].append(f"[{WORKER_NAME}] skipped empty task")
        state["worker_io_logs"].append(worker_io)
        return state

    try:
        chunks = search_kb(task, top_k=top_k)
        sources = sorted({chunk.get("source", "unknown") for chunk in chunks})

        state["retrieved_chunks"] = chunks
        state["retrieved_sources"] = sources

        worker_io["output"] = {
            "chunks_count": len(chunks),
            "sources": sources,
            "top_score": chunks[0]["score"] if chunks else 0.0,
        }
        state["history"].append(
            f"[{WORKER_NAME}] retrieved {len(chunks)} chunks from {len(sources)} sources"
        )
    except Exception as exc:
        state["retrieved_chunks"] = []
        state["retrieved_sources"] = []
        worker_io["error"] = {"code": "RETRIEVAL_FAILED", "reason": str(exc)}
        state["history"].append(f"[{WORKER_NAME}] error: {exc}")

    state["worker_io_logs"].append(worker_io)
    return state
