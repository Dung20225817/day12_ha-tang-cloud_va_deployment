"""Supervisor-worker graph adapted from Day09 for Day12 production service."""
from __future__ import annotations

import time
from typing import Literal

from app.orchestrator.types import AgentState, make_initial_state
from app.orchestrator.workers.policy_tool import run as policy_tool_run
from app.orchestrator.workers.retrieval import run as retrieval_run
from app.orchestrator.workers.synthesis import run as synthesis_run


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def supervisor_node(state: AgentState) -> AgentState:
    task = state.get("task", "")
    text = task.lower()

    incident_keywords = (
        "p1",
        "sla",
        "incident",
        "ticket",
        "escalation",
        "sự cố",
        "su co",
    )
    access_keywords = (
        "access",
        "cấp quyền",
        "cap quyen",
        "level",
        "admin",
        "contractor",
    )
    policy_keywords = (
        "refund",
        "hoàn tiền",
        "hoan tien",
        "flash sale",
        "license",
        "store credit",
    )

    has_incident = _contains_any(text, incident_keywords)
    has_access = _contains_any(text, access_keywords)
    has_policy = _contains_any(text, policy_keywords)

    if has_incident and has_access:
        route = "multi_hop"
        reason = "incident/SLA and access intent detected, run retrieval + policy + synthesis"
        needs_tool = True
        top_k = 8
    elif has_incident:
        route = "retrieval_worker"
        reason = "incident/SLA intent detected, use retrieval + synthesis with broader context"
        needs_tool = False
        top_k = 8
    elif has_policy or has_access:
        route = "policy_tool_worker"
        reason = "policy/access intent detected, policy worker may call MCP tools"
        needs_tool = True
        top_k = 6
    else:
        route = "retrieval_worker"
        reason = "default informational route: retrieval then synthesis"
        needs_tool = False
        top_k = 5

    state["supervisor_route"] = route
    state["route_reason"] = reason
    state["needs_tool"] = needs_tool
    state["risk_high"] = _contains_any(text, ("p1", "khẩn cấp", "khan cap", "emergency"))
    state["retrieval_top_k"] = top_k
    state.setdefault("history", []).append(f"[supervisor] route={route} reason={reason}")
    return state


def route_decision(state: AgentState) -> Literal[
    "retrieval_worker", "policy_tool_worker", "human_review", "multi_hop"
]:
    route = state.get("supervisor_route") or "retrieval_worker"
    if route in {"retrieval_worker", "policy_tool_worker", "human_review", "multi_hop"}:
        return route
    return "retrieval_worker"


def human_review_node(state: AgentState) -> AgentState:
    state["hitl_triggered"] = True
    state.setdefault("workers_called", []).append("human_review")
    state.setdefault("history", []).append("[human_review] fallback path used")
    return state


def run_graph(task: str, history_lines: list[str] | None = None) -> AgentState:
    state = make_initial_state(task, history_lines)
    t0 = time.time()

    state = supervisor_node(state)
    route = route_decision(state)

    if route == "human_review":
        state = human_review_node(state)
        state = retrieval_run(state)
        state = synthesis_run(state)
    elif route == "multi_hop":
        state = retrieval_run(state)
        state = policy_tool_run(state)
        state = synthesis_run(state)
    elif route == "policy_tool_worker":
        state = policy_tool_run(state)
        state = synthesis_run(state)
    else:
        state = retrieval_run(state)
        state = synthesis_run(state)

    state["workers_called"] = list(dict.fromkeys(state.get("workers_called") or []))
    state["latency_ms"] = int((time.time() - t0) * 1000)
    state.setdefault("history", []).append(f"[graph] completed in {state['latency_ms']}ms")
    return state
