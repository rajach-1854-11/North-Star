# API Smoke Summary

**Run ID:** 20251003-194841  
**Result:** FAIL  
**Tenant:** tenant1  

## Checklist

- Env guardrails ✅: Postgres host=northstar-db.c9gkqkueux84.eu-north-1.rds.amazonaws.com; Qdrant URL validated; Redis URL uses TLS; Cerebras provider enforced
- Postgres connectivity ✅: SELECT 1 succeeded
- Qdrant connectivity ✅: HTTP 200
- Redis connectivity ✅: PING succeeded
- API readiness ✅: openapi.json reachable
- Auth token ❌: 
- Project upsert ❌: 
- Upload ❌: 
- Retrieve ❌: 
- Staff recommend ❌: 
- Onboarding generate ❌: 
- Agent query ❌: 
- Skills profile ❌: 
- Audit ❌: 
- GitHub webhook ❌: 

## Triage

- Auth token: see logs
- Project upsert: see logs
- Upload: see logs
- Retrieve: see logs
- Staff recommend: see logs
- Onboarding generate: see logs
- Agent query: see logs
- Skills profile: see logs
- Audit: see logs
- GitHub webhook: see logs

## Notes

- Unhandled error: [WinError 10054] An existing connection was forcibly closed by the remote host
