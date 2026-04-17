"""Shared state definitions for the orchestration graph."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    task: str
    route_reason: str
    risk_high: bool
    needs_tool: bool
    hitl_triggered: bool
    retrieved_chunks: list[dict[str, Any]]
    retrieved_sources: list[str]
    policy_result: dict[str, Any]
    mcp_tools_used: list[dict[str, Any]]
    final_answer: str
    sources: list[str]
    confidence: float
    history: list[str]
    workers_called: list[str]
    supervisor_route: str
    latency_ms: int
    run_id: str
    worker_io_logs: list[dict[str, Any]]
    retrieval_top_k: int


def make_initial_state(task: str, history_lines: list[str] | None = None) -> AgentState:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    return {
        "task": task,
        "route_reason": "",
        "risk_high": False,
        "needs_tool": False,
        "hitl_triggered": False,
        "retrieved_chunks": [],
        "retrieved_sources": [],
        "policy_result": {},
        "mcp_tools_used": [],
        "final_answer": "",
        "sources": [],
        "confidence": 0.0,
        "history": history_lines[:] if history_lines else [],
        "workers_called": [],
        "supervisor_route": "",
        "latency_ms": 0,
        "run_id": f"run_{timestamp}",
        "worker_io_logs": [],
        "retrieval_top_k": 5,
    }
