# Day 12 Lab - Mission Answers

Student Name: Phạm Quốc Dũng  
SID: 2A202600490  
Date: 2026-04-17

Repository: https://github.com/Dung20225817/day12_ha-tang-cloud_va_deployment

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found in 01-localhost-vs-production/develop/app.py
1. Hardcoded OPENAI API key in source code.
2. Hardcoded DATABASE_URL with username and password.
3. DEBUG mode set directly in code.
4. Logging secrets with print (key leakage risk).
5. No health check endpoint for platform monitoring.
6. Fixed localhost binding (not container/cloud friendly).
7. Fixed port 8000 (does not read PORT from env).
8. reload=True in runtime path (unsafe for production runtime).

### Exercise 1.2: Basic version observation
- The basic app can answer requests locally.
- It is functional but not production-ready due to security/config/observability gaps.

### Exercise 1.3: Comparison table (basic vs advanced)

| Feature | Basic | Advanced | Why Important? |
|---|---|---|---|
| Config | Hardcoded | Environment variables | Supports dev/staging/prod safely and avoids committing secrets |
| Health check | Missing | /health and /ready | Allows orchestrator restart/routing decisions |
| Logging | print() | Structured JSON logging | Better filtering, alerting, and incident analysis |
| Shutdown | Abrupt | Graceful shutdown | Reduces dropped in-flight requests |
| Host/Port | localhost:8000 fixed | 0.0.0.0 + PORT env | Works in Docker/cloud runtime |

## Part 2: Docker

### Exercise 2.1: Dockerfile questions
1. Base image (develop): python:3.11
2. Working directory: /app
3. requirements.txt is copied before app code to maximize Docker layer cache.
4. CMD is default executable/args that can be overridden; ENTRYPOINT defines fixed executable behavior.

### Exercise 2.2: Build and run
- Develop image built and tested locally.
- Observed image size:
  - agent-develop:latest = 1.66GB

### Exercise 2.3: Multi-stage build analysis
- Stage 1 (builder): installs build tools and Python dependencies.
- Stage 2 (runtime): copies only runtime environment and app source.
- Measured image sizes:
  - Develop: 1.66GB
  - Advanced/Production: 236MB
  - Reduction: about 85.8%

### Exercise 2.4: Docker Compose architecture

Client -> Nginx -> Agent -> Redis

(02-docker/production also includes Qdrant in that stack.)

Communication:
- Client sends HTTP requests to Nginx.
- Nginx reverse-proxies/load-balances to agent service.
- Agent uses Redis for cache/session/rate-related state.

## Part 3: Cloud Deployment (Railway only)

### Exercise 3.1: Railway deployment
- Scope note: Part 3 in this submission is Railway-only (Render/Cloud Run not required).
- Deployment executed with Railway CLI (`npx @railway/cli`).
- Public URL: https://day12-agent-api-production.up.railway.app
- Latest deployment status: SUCCESS (`3667bb13-6ec4-46c2-83f2-dcc2733988e8`).
- Public checks (2026-04-17):
  - `GET /health` -> 200
  - `GET /ready` -> 200
  - `GET /ui` -> 200 (simple HTML UI for manual smoke tests)
  - `GET /kb-status` (with API key) -> 200, `chunk_count=69`, `source_count=5`
  - `POST /ask` without API key -> 401
  - `POST /ask` with valid Railway secret key -> 200
  - `GET /trace/{user_id}` with valid key -> 200
- Cloud parity note:
  - Initial cloud issue: KB docs folder existed but empty, causing `sources=[]`.
  - Final fix: embedded KB fallback in `app/orchestrator/knowledge_base.py` + startup diagnostics (`kb_chunk_count`, `kb_using_embedded_docs`).
- Screenshot targets in repository:
  - `screenshots/dashboard.png`
  - `screenshots/running.png`
  - `screenshots/test.png`

## Part 4: API Security

### Exercise 4.1-4.3: Test results (final stack)
- Without API key: 401
- With valid API key: 200
- Rate limit test (12 requests same user):
  - RATE_CODES=200,200,200,200,200,200,200,200,200,200,429,429

### Exercise 4.4: Cost guard implementation
Approach implemented in app/cost_guard.py:
- Budget key pattern: budget:{user_id}:{YYYY-MM}
- Read current spend from Redis.
- If current + estimated_cost > MONTHLY_BUDGET_USD -> raise HTTP 402.
- Otherwise increment spend with INCRBYFLOAT and set TTL (32 days).
- Admin users can be bypassed via ADMIN_USER_IDS.

## Part 5: Scaling and Reliability

### Exercise 5.1: Health/readiness
- /health returns service liveness plus redis state.
- /ready returns 200 only when app is ready, Redis is reachable, and shutdown mode is off.

### Exercise 5.2: Graceful shutdown
- SIGTERM handler sets shutting_down flag.
- Middleware returns 503 for new traffic during shutdown window.
- Existing requests are handled by Uvicorn graceful timeout.

### Exercise 5.3: Stateless design
- Conversation state is stored in Redis list keys: history:{user_id}
- No in-memory conversation dict is used for business state.

### Exercise 5.4: Load balancing
- Nginx service routes requests to agent upstream in docker-compose stack.
- Agent can be scaled with docker compose --scale agent=3.

### Exercise 5.5: Stateless verification
- Sequential requests with same user preserved history across calls.
- Example observed:
  - First call history_items=2
  - Second call history_items=4

## Part 6 readiness summary

Local production checks passed:
- check_production_ready.py = 20/20 (100%)
- Docker image build succeeded: day12-final:latest
- Compose stack up with redis healthy, agent healthy, nginx running
- Endpoint smoke tests passed: health=200, ready=200, unauthorized=401, authorized ask=200

Cloud deployment checks passed:
- Railway deployment is reachable on public domain
- Health/readiness/authenticated request behavior matches local production expectations
- Day09-style orchestration validated on cloud:
  - SLA query route `retrieval_worker` with source `sla_p1_2026.txt`
  - Multi-hop query route `multi_hop` with sources `access_control_sop.txt` + `sla_p1_2026.txt`
