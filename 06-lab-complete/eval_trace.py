"""Evaluate Day09-style orchestration behavior inside 06-lab-complete."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from app.orchestrator.graph import run_graph

ROOT = Path(__file__).resolve().parent
DEFAULT_TEST_FILE = ROOT / "app" / "orchestrator" / "data" / "test_questions.json"
ARTIFACTS_DIR = ROOT / "artifacts"
TRACES_DIR = ARTIFACTS_DIR / "traces"
REPORT_FILE = ARTIFACTS_DIR / "eval_report.json"


def _load_questions(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, dict) and "questions" in data:
        return data["questions"]
    if isinstance(data, list):
        return data
    raise ValueError(f"Unsupported questions format in {path}")


def _save_trace(trace: dict) -> Path:
    TRACES_DIR.mkdir(parents=True, exist_ok=True)
    run_id = trace.get("run_id", f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}")
    output_path = TRACES_DIR / f"{run_id}.json"
    output_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def _summarize(results: list[dict]) -> dict:
    total = len(results)
    succeeded = [item for item in results if not item.get("error")]
    routes = {}
    workers = {}
    confidence_values = []
    latency_values = []

    for item in succeeded:
        state = item["state"]
        route = state.get("supervisor_route", "unknown")
        routes[route] = routes.get(route, 0) + 1

        for worker in state.get("workers_called", []):
            workers[worker] = workers.get(worker, 0) + 1

        confidence_values.append(float(state.get("confidence", 0.0) or 0.0))
        latency_values.append(int(state.get("latency_ms", 0) or 0))

    avg_confidence = round(sum(confidence_values) / len(confidence_values), 3) if confidence_values else 0.0
    avg_latency = round(sum(latency_values) / len(latency_values), 2) if latency_values else 0.0

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_questions": total,
        "successful_runs": len(succeeded),
        "failed_runs": total - len(succeeded),
        "routing_distribution": routes,
        "worker_call_counts": workers,
        "avg_confidence": avg_confidence,
        "avg_latency_ms": avg_latency,
    }


def run_eval(test_file: Path, persist_traces: bool = True) -> dict:
    questions = _load_questions(test_file)
    results = []

    print(f"Running {len(questions)} questions from {test_file}")

    for index, item in enumerate(questions, start=1):
        question = item.get("question", "")
        qid = item.get("id", f"q{index:02d}")

        try:
            state = run_graph(question)
            if persist_traces:
                _save_trace(state)

            print(
                f"[{index:02d}] {qid} route={state.get('supervisor_route')} "
                f"workers={state.get('workers_called', [])} conf={state.get('confidence')}"
            )
            results.append({"id": qid, "state": state, "error": None})
        except Exception as exc:
            print(f"[{index:02d}] {qid} ERROR: {exc}")
            results.append({"id": qid, "state": None, "error": str(exc)})

    summary = _summarize(results)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("---")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved report to {REPORT_FILE}")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate Day09-style supervisor-worker traces")
    parser.add_argument("--test-file", type=Path, default=DEFAULT_TEST_FILE)
    parser.add_argument("--no-trace", action="store_true", help="Skip per-run trace persistence")
    args = parser.parse_args()

    run_eval(args.test_file, persist_traces=not args.no_trace)
