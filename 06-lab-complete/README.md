# Lab 12 Complete - Production Agent (Day09 Upgrade)

This folder is the final submission app that combines Day 12 production hardening and Day 09 supervisor-worker orchestration.

## Implemented Features

- Multi-stage Docker build with non-root runtime user
- API key authentication via header `X-API-Key`
- Rate limiting: 10 requests per minute per user
- Cost guard: 10 USD per month per user
- Health and readiness endpoints
- Graceful shutdown behavior
- Stateless history and trace storage in Redis
- Nginx load balancing for horizontal scaling
- Supervisor-worker orchestration routes: retrieval_worker, policy_tool_worker, multi_hop
- Operational endpoints: `GET /ui`, `GET /trace/{user_id}`, `GET /kb-status`

## Main Files

- API entrypoint: `app/main.py`
- Security and controls: `app/auth.py`, `app/rate_limiter.py`, `app/cost_guard.py`, `app/config.py`
- Orchestration: `app/orchestrator/graph.py`
- Workers: `app/orchestrator/workers/retrieval.py`, `app/orchestrator/workers/policy_tool.py`, `app/orchestrator/workers/synthesis.py`
- Tool server: `app/orchestrator/mcp_server.py`
- KB search: `app/orchestrator/knowledge_base.py`
- KB docs: `app/orchestrator/data/docs/*.txt`
- Test questions: `app/orchestrator/data/test_questions.json`

Note: `knowledge_base.py` has embedded-doc fallback. If cloud packaging misses docs files, retrieval still works and `GET /kb-status` reports `using_embedded_docs=true`.

## Run Locally

1. Open terminal in this folder.

```bash
cd 06-lab-complete
```

1. Create local environment file.

```bash
copy .env.example .env
```

1. Build and run stack.

```bash
docker compose up -d --build
```

1. Quick smoke tests.

```bash
curl http://localhost/health
curl http://localhost/ready
curl http://localhost/ui
curl -H "X-API-Key: secret-key-123" http://localhost/kb-status
```

1. Ask endpoint test.

```bash
curl -X POST http://localhost/ask \
  -H "X-API-Key: secret-key-123" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"demo","question":"SLA ticket P1 response and resolution time"}'
```

1. Trace endpoint test.

```bash
curl -H "X-API-Key: secret-key-123" "http://localhost/trace/demo?limit=5"
```

## Validation Targets

- Auth without key returns 401
- First 10 requests return 200 and later requests return 429
- SLA query should route to retrieval_worker and return non-empty sources
- Multi-hop query should route to multi_hop and return sources from multiple docs

## Orchestrator Evaluation

Host run:

```bash
python eval_trace.py
```

Container quick check:

```bash
docker compose exec -T agent python -c "import json; from pathlib import Path; from app.orchestrator.graph import run_graph; qs=json.loads(Path('/app/app/orchestrator/data/test_questions.json').read_text(encoding='utf-8')); ok=sum(1 for q in qs if (run_graph(q['question'],[]).get('final_answer') or '').strip()); print(f'EVAL_SUCCESS={ok}/{len(qs)}')"
```

## Deploy

- Railway config: `railway.toml`
- Render config: `render.yaml`

Required cloud env vars:

- AGENT_API_KEY
- REDIS_URL
- RATE_LIMIT_PER_MINUTE
- MONTHLY_BUDGET_USD
- HISTORY_MAX_MESSAGES
- HISTORY_TTL_SECONDS
- OPENAI_API_KEY (optional)

## Production Checker

```bash
python check_production_ready.py
```

Expected result: all required checks pass.
