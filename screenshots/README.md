# Screenshots Needed

Add real screenshots before final submission:

1. `dashboard.png`
- Railway project dashboard showing service status = Running.

2. `running.png`
- Public URL in browser with a successful endpoint response (`/health` or `/ready`).

3. `test.png`
- Terminal output showing auth/rate-limit smoke tests (401 and 200 at minimum).

Suggested command capture source:

```powershell
curl.exe -s -o NUL -w "PUBLIC_HEALTH=%{http_code}`n" https://day12-agent-api-production.up.railway.app/health
curl.exe -s -o NUL -w "PUBLIC_READY=%{http_code}`n" https://day12-agent-api-production.up.railway.app/ready
```
