"""In-process MCP-like tool server adapted from Day09 lab."""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from app.orchestrator.knowledge_base import search_kb

TOOL_SCHEMAS = {
    "search_kb": {
        "name": "search_kb",
        "description": "Search internal KB chunks by lexical relevance",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    "get_ticket_info": {
        "name": "get_ticket_info",
        "description": "Get mock ticket context for incident workflow",
        "inputSchema": {
            "type": "object",
            "properties": {"ticket_id": {"type": "string"}},
            "required": ["ticket_id"],
        },
    },
    "check_access_permission": {
        "name": "check_access_permission",
        "description": "Validate access request approvals and emergency policy",
        "inputSchema": {
            "type": "object",
            "properties": {
                "access_level": {"type": "integer"},
                "requester_role": {"type": "string"},
                "is_emergency": {"type": "boolean", "default": False},
            },
            "required": ["access_level", "requester_role"],
        },
    },
    "create_ticket": {
        "name": "create_ticket",
        "description": "Create a mock Jira ticket for workflow simulation",
        "inputSchema": {
            "type": "object",
            "properties": {
                "priority": {"type": "string"},
                "title": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["priority", "title"],
        },
    },
}

MOCK_TICKETS = {
    "P1-LATEST": {
        "ticket_id": "IT-9847",
        "priority": "P1",
        "status": "in_progress",
        "assignee": "oncall@company.internal",
        "created_at": "2026-04-17T02:00:00+00:00",
        "sla_deadline": "2026-04-17T06:00:00+00:00",
        "notifications_sent": [
            "slack:#incident-p1",
            "email:incident@company.internal",
            "pagerduty:oncall",
        ],
    }
}

ACCESS_RULES = {
    1: {
        "required_approvers": ["Line Manager"],
        "processing_days": 1,
        "emergency_can_bypass": False,
    },
    2: {
        "required_approvers": ["Line Manager", "IT Admin"],
        "processing_days": 2,
        "emergency_can_bypass": True,
        "emergency_note": "Level 2 can be granted temporarily for emergency fix with dual approval.",
    },
    3: {
        "required_approvers": ["Line Manager", "IT Admin", "IT Security"],
        "processing_days": 3,
        "emergency_can_bypass": False,
        "emergency_note": "Level 3 has no emergency bypass.",
    },
    4: {
        "required_approvers": ["IT Manager", "CISO"],
        "processing_days": 5,
        "emergency_can_bypass": False,
        "extra_requirements": "Security training is mandatory.",
    },
}


def list_tools() -> list[dict[str, Any]]:
    return [copy.deepcopy(tool_schema) for tool_schema in TOOL_SCHEMAS.values()]


def tool_search_kb(query: str, top_k: int = 5) -> dict[str, Any]:
    chunks = search_kb(query, top_k=top_k)
    sources = sorted({chunk.get("source", "unknown") for chunk in chunks})
    return {"chunks": chunks, "sources": sources, "total_found": len(chunks)}


def tool_get_ticket_info(ticket_id: str) -> dict[str, Any]:
    ticket = MOCK_TICKETS.get(str(ticket_id).strip().upper())
    if ticket:
        return dict(ticket)
    return {
        "error": f"Ticket '{ticket_id}' not found",
        "available_mock_ids": sorted(MOCK_TICKETS.keys()),
    }


def tool_check_access_permission(
    access_level: int,
    requester_role: str,
    is_emergency: bool = False,
) -> dict[str, Any]:
    rule = ACCESS_RULES.get(int(access_level))
    if not rule:
        return {"error": "Unsupported access_level. Expected 1..4"}

    requester_role = str(requester_role or "employee").lower()
    can_grant = True
    notes: list[str] = []

    if requester_role == "contractor" and int(access_level) >= 3:
        can_grant = False
        notes.append("Contractor cannot directly receive level >=3 access without internal escalation.")

    if is_emergency and not rule.get("emergency_can_bypass", False):
        notes.append(rule.get("emergency_note", "No emergency bypass."))

    if is_emergency and rule.get("emergency_can_bypass", False):
        notes.append(rule.get("emergency_note", "Emergency temporary grant is allowed."))

    return {
        "access_level": int(access_level),
        "requester_role": requester_role,
        "can_grant": can_grant,
        "required_approvers": list(rule.get("required_approvers", [])),
        "approver_count": len(rule.get("required_approvers", [])),
        "processing_days": rule.get("processing_days"),
        "emergency_override": bool(is_emergency and rule.get("emergency_can_bypass", False)),
        "extra_requirements": rule.get("extra_requirements"),
        "source": "access_control_sop.txt",
        "notes": notes,
    }


def tool_create_ticket(priority: str, title: str, description: str = "") -> dict[str, Any]:
    priority = str(priority or "P3").upper()
    if priority not in {"P1", "P2", "P3", "P4"}:
        return {"error": "priority must be one of P1/P2/P3/P4"}

    created_at = datetime.now(timezone.utc).isoformat()
    ticket_id = f"IT-{9500 + abs(hash(title + created_at)) % 400}"
    return {
        "ticket_id": ticket_id,
        "priority": priority,
        "title": title,
        "description": description[:300],
        "status": "open",
        "created_at": created_at,
        "url": f"https://jira.company.internal/browse/{ticket_id}",
        "note": "Mock ticket generated by Day12 orchestrator",
    }


def _validate_required(tool_name: str, tool_input: dict[str, Any]) -> str | None:
    schema = TOOL_SCHEMAS[tool_name].get("inputSchema", {})
    required = schema.get("required", [])
    missing = [field for field in required if field not in tool_input]
    if missing:
        return f"Missing required fields for {tool_name}: {missing}"
    return None


def dispatch_tool(tool_name: str, tool_input: dict[str, Any] | None = None) -> dict[str, Any]:
    tool_input = dict(tool_input or {})

    registry = {
        "search_kb": tool_search_kb,
        "get_ticket_info": tool_get_ticket_info,
        "check_access_permission": tool_check_access_permission,
        "create_ticket": tool_create_ticket,
    }

    if tool_name not in registry:
        return {
            "error": f"Tool '{tool_name}' is not available",
            "available_tools": sorted(registry.keys()),
        }

    required_error = _validate_required(tool_name, tool_input)
    if required_error:
        return {"error": required_error, "schema": TOOL_SCHEMAS[tool_name]["inputSchema"]}

    try:
        return registry[tool_name](**tool_input)
    except Exception as exc:
        return {"error": f"Tool '{tool_name}' failed: {exc}"}
