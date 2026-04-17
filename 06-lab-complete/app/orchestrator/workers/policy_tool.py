"""Policy/tool worker with MCP integrations adapted from Day09."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from app.orchestrator.mcp_server import dispatch_tool

WORKER_NAME = "policy_tool_worker"
POLICY_SOURCE = "policy_refund_v4.txt"

FLASH_SALE_KEYWORDS = ("flash sale", "flashsale", "mã giảm giá đặc biệt", "ma giam gia dac biet")
DIGITAL_KEYWORDS = ("license", "subscription", "kỹ thuật số", "ky thuat so")
ACTIVATED_KEYWORDS = ("đã kích hoạt", "da kich hoat", "đăng ký tài khoản", "dang ky tai khoan")
REFUND_KEYWORDS = ("hoàn tiền", "hoan tien", "refund", "store credit")
ACCESS_KEYWORDS = ("access", "cấp quyền", "cap quyen", "level 1", "level 2", "level 3", "level 4", "admin")
TICKET_KEYWORDS = ("ticket", "p1", "incident", "sự cố", "su co")
CREATE_TICKET_KEYWORDS = ("tạo ticket", "tao ticket", "create ticket", "mở ticket", "mo ticket")
EMERGENCY_KEYWORDS = ("emergency", "khẩn cấp", "khan cap", "2am", "urgent")


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def _extract_dates_ddmmyyyy(text: str) -> list[tuple[int, int, int]]:
    dates = []
    for d, m, y in re.findall(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", text):
        try:
            dates.append((int(d), int(m), int(y)))
        except ValueError:
            continue
    return dates


def _append_tool_call(state: dict, tool_name: str, payload: dict) -> dict:
    result = dispatch_tool(tool_name, payload)
    state.setdefault("mcp_tools_used", []).append(
        {
            "tool": tool_name,
            "input": payload,
            "output": result,
            "error": {"code": "MCP_TOOL_ERROR", "reason": result.get("error")} if result.get("error") else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    return result


def _intent_flags(task_lower: str) -> dict[str, bool]:
    return {
        "refund": _contains_any(task_lower, REFUND_KEYWORDS),
        "access": _contains_any(task_lower, ACCESS_KEYWORDS),
        "incident": _contains_any(task_lower, TICKET_KEYWORDS),
    }


def _filter_chunks_by_intent(chunks: list[dict], task_lower: str) -> list[dict]:
    """Keep chunks aligned with query intent to avoid cross-doc false positives."""
    if not chunks:
        return []

    flags = _intent_flags(task_lower)
    allowed_sources: set[str] = set()

    if flags["refund"]:
        allowed_sources.add("policy_refund_v4.txt")
    if flags["access"]:
        allowed_sources.add("access_control_sop.txt")
    if flags["incident"]:
        allowed_sources.add("sla_p1_2026.txt")

    if not allowed_sources:
        return chunks

    filtered = [chunk for chunk in chunks if chunk.get("source") in allowed_sources]
    return filtered or chunks


def _policy_analysis(task: str, chunks: list[dict]) -> dict:
    task_lower = (task or "").lower()
    context = " ".join(chunk.get("text", "") for chunk in chunks).lower()
    flags = _intent_flags(task_lower)

    exceptions: list[dict] = []
    if _contains_any(task_lower, FLASH_SALE_KEYWORDS) or (
        flags["refund"] and _contains_any(context, FLASH_SALE_KEYWORDS)
    ):
        exceptions.append(
            {
                "type": "flash_sale_exception",
                "rule": "Đơn hàng Flash Sale không được hoàn tiền.",
                "source": POLICY_SOURCE,
            }
        )

    if _contains_any(task_lower, DIGITAL_KEYWORDS):
        exceptions.append(
            {
                "type": "digital_product_exception",
                "rule": "Sản phẩm kỹ thuật số (license key, subscription) không được hoàn tiền.",
                "source": POLICY_SOURCE,
            }
        )

    if _contains_any(task_lower, ACTIVATED_KEYWORDS):
        exceptions.append(
            {
                "type": "activated_exception",
                "rule": "Sản phẩm đã kích hoạt hoặc đăng ký tài khoản không được hoàn tiền.",
                "source": POLICY_SOURCE,
            }
        )

    policy_version_note = ""
    policy_name = "refund_policy_v4"
    for day, month, year in _extract_dates_ddmmyyyy(task_lower + " " + context):
        if (year, month, day) < (2026, 2, 1):
            policy_name = "refund_policy_v3"
            policy_version_note = (
                "Phát hiện mốc thời gian trước 01/02/2026, cần áp dụng policy v3. "
                "Tài liệu hiện tại chỉ chứa chi tiết policy v4 nên cần xác nhận thêm với CS Team."
            )
            break

    sources = sorted({chunk.get("source", "unknown") for chunk in chunks})
    policy_applies = (len(exceptions) == 0) and not policy_version_note

    return {
        "policy_applies": policy_applies,
        "policy_name": policy_name,
        "exceptions_found": exceptions,
        "source": sources,
        "policy_version_note": policy_version_note,
        "intent_flags": flags,
    }


def _infer_access_level(task_lower: str) -> int:
    match = re.search(r"level\s*(\d)", task_lower)
    if match:
        return int(match.group(1))
    if "admin" in task_lower:
        return 4
    return 2


def _infer_role(task_lower: str) -> str:
    if "contractor" in task_lower:
        return "contractor"
    if "vendor" in task_lower:
        return "vendor"
    return "employee"


def run(state: dict) -> dict:
    task = state.get("task", "")
    task_lower = task.lower()
    chunks = list(state.get("retrieved_chunks") or [])
    needs_tool = bool(state.get("needs_tool"))

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state.setdefault("worker_io_logs", [])
    state.setdefault("mcp_tools_used", [])

    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {"task": task, "chunks_count": len(chunks), "needs_tool": needs_tool},
        "output": None,
        "error": None,
    }

    try:
        flags = _intent_flags(task_lower)

        if needs_tool and not chunks:
            query = task
            if flags["refund"] and not flags["access"]:
                query = f"{task} refund policy"
            elif flags["access"] and not flags["incident"]:
                query = f"{task} access control sop"
            elif flags["incident"]:
                query = f"{task} sla p1 incident"

            kb_result = _append_tool_call(
                state,
                "search_kb",
                {"query": query, "top_k": int(state.get("retrieval_top_k", 5) or 5)},
            )
            chunks = kb_result.get("chunks", []) if isinstance(kb_result, dict) else []
            if chunks:
                state["retrieved_chunks"] = chunks
                state["retrieved_sources"] = sorted({chunk.get("source", "unknown") for chunk in chunks})

        chunks = _filter_chunks_by_intent(chunks, task_lower)
        state["retrieved_chunks"] = chunks
        state["retrieved_sources"] = sorted({chunk.get("source", "unknown") for chunk in chunks}) if chunks else []

        policy_result = _policy_analysis(task, chunks)
        state["policy_result"] = policy_result

        if needs_tool and _contains_any(task_lower, TICKET_KEYWORDS):
            ticket_info = _append_tool_call(state, "get_ticket_info", {"ticket_id": "P1-LATEST"})
            if isinstance(ticket_info, dict) and not ticket_info.get("error"):
                state["policy_result"]["ticket_info"] = ticket_info

        if needs_tool and _contains_any(task_lower, ACCESS_KEYWORDS):
            access_info = _append_tool_call(
                state,
                "check_access_permission",
                {
                    "access_level": _infer_access_level(task_lower),
                    "requester_role": _infer_role(task_lower),
                    "is_emergency": _contains_any(task_lower, EMERGENCY_KEYWORDS),
                },
            )
            if isinstance(access_info, dict) and not access_info.get("error"):
                state["policy_result"]["access_permission"] = access_info

        if needs_tool and _contains_any(task_lower, CREATE_TICKET_KEYWORDS):
            _append_tool_call(
                state,
                "create_ticket",
                {
                    "priority": "P1" if "p1" in task_lower else "P2",
                    "title": " ".join(task.split())[:80],
                    "description": " ".join(task.split())[:240],
                },
            )

        worker_io["output"] = {
            "policy_applies": state["policy_result"].get("policy_applies"),
            "exceptions_count": len(state["policy_result"].get("exceptions_found") or []),
            "mcp_calls": len(state.get("mcp_tools_used") or []),
            "intent_flags": state["policy_result"].get("intent_flags", {}),
        }

        state["history"].append(
            f"[{WORKER_NAME}] policy_applies={state['policy_result'].get('policy_applies')} "
            f"exceptions={len(state['policy_result'].get('exceptions_found') or [])}"
        )
    except Exception as exc:
        worker_io["error"] = {"code": "POLICY_CHECK_FAILED", "reason": str(exc)}
        state["policy_result"] = {"error": str(exc)}
        state["history"].append(f"[{WORKER_NAME}] error: {exc}")

    state["worker_io_logs"].append(worker_io)
    return state
