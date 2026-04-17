# Deployment Information

Student Name: Phạm Quốc Dũng  
SID: 2A202600490  
Date: 2026-04-17

Repository: https://github.com/Dung20225817/day12_ha-tang-cloud_va_deployment

## Public URL
https://day12-agent-api-production.up.railway.app

## Platform
Railway (Dockerfile deployment) + Railway Redis service

## Part 3 Scope
- Railway deployment only (Render and Cloud Run are not required for this submission).

## Deployment Status
- Latest deployment: `3667bb13-6ec4-46c2-83f2-dcc2733988e8` -> SUCCESS
- Previous deployment: `bf8c44b9-f93b-4551-a738-b1e739ee9cfe` -> REMOVED
- Earlier issue: cloud runtime had empty KB docs directory (`chunk_count=0`, `sources=[]`).
- Final fix: embedded KB fallback added in `app/orchestrator/knowledge_base.py` + startup diagnostics.

## Public Smoke Test Results (Cloud)
Executed on: 2026-04-17

- PUBLIC_HEALTH=200
- PUBLIC_READY=200
- PUBLIC_UI=200
- PUBLIC_KB_STATUS=200
- PUBLIC_ASK_NO_KEY=401
- PUBLIC_ASK_AUTH=200 (validated using real Railway secret key; key is hidden)
- PUBLIC_TRACE=200

Sample `/kb-status` response:
```json
{
  "docs_dir": "/app/app/orchestrator/data/docs",
  "using_embedded_docs": true,
  "chunk_count": 69,
  "source_count": 5,
  "sources": [
    "access_control_sop.txt",
    "hr_leave_policy.txt",
    "it_helpdesk_faq.txt",
    "policy_refund_v4.txt",
    "sla_p1_2026.txt"
  ]
}
```

Sample `/ask` response (authorized, SLA question):
```json
{
  "route": "retrieval_worker",
  "workers_called": ["retrieval_worker", "synthesis_worker"],
  "sources": ["sla_p1_2026.txt"],
  "answer": "SLA P1 có phản hồi ban đầu trong 15 phút; thời gian xử lý/khắc phục: 4 giờ; ..."
}
```

Sample `/ask` response (authorized, multi-hop question):
```json
{
  "route": "multi_hop",
  "workers_called": ["retrieval_worker", "policy_tool_worker", "synthesis_worker"],
  "sources": ["access_control_sop.txt", "sla_p1_2026.txt"],
  "answer": "... notify stakeholders theo SLA ... Level 2 access tạm thời ..."
}
```

## Test Commands (Public URL)

### Health
```bash
curl https://day12-agent-api-production.up.railway.app/health
```

### Readiness
```bash
curl https://day12-agent-api-production.up.railway.app/ready
```

### UI
```bash
curl -I https://day12-agent-api-production.up.railway.app/ui
```

### KB Status
```bash
curl -H "X-API-Key: <AGENT_API_KEY>" \
  https://day12-agent-api-production.up.railway.app/kb-status
```

### Ask without API key (expect 401)
```bash
curl -X POST https://day12-agent-api-production.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"Hello"}'
```

### Trace endpoint
```bash
curl -H "X-API-Key: <AGENT_API_KEY>" \
  "https://day12-agent-api-production.up.railway.app/trace/test?limit=3"
```

### Ask with API key (expect 200)
```bash
curl -X POST https://day12-agent-api-production.up.railway.app/ask \
  -H "X-API-Key: <AGENT_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"Hello"}'
```

## Environment Variables Set (Railway)
- ENVIRONMENT=production
- DEBUG=false
- AGENT_API_KEY=<set-in-railway-secret>
- ADMIN_USER_IDS=admin,2A202600490
- OPENAI_API_KEY=
- LLM_MODEL=gpt-4o-mini
- REDIS_URL (from Railway Redis)
- RATE_LIMIT_PER_MINUTE=10
- MONTHLY_BUDGET_USD=10
- HISTORY_MAX_MESSAGES=20
- HISTORY_TTL_SECONDS=86400
- ALLOWED_ORIGINS=*

## Local Validation (Before Cloud Deploy)
- check_production_ready.py = 20/20 (100%)
- Docker image `day12-final:latest` built successfully
- Compose smoke test passed (health/ready/auth/rate-limit)
- Container eval quick check: `EVAL_SUCCESS=15/15`

## Screenshots
- Required files for final submission (pending add):
  - [ ] `screenshots/dashboard.png` - Railway dashboard with service status
  - [ ] `screenshots/running.png` - Browser test of public endpoint
  - [ ] `screenshots/test.png` - Terminal smoke test outputs
