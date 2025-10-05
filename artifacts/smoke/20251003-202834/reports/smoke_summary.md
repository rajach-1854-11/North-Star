# API Smoke Summary

**Run ID:** 20251003-202834  
**Result:** FAIL  
**Tenant:** tenant1  

## Checklist

- Env guardrails ✅: Postgres host=northstar-db.c9gkqkueux84.eu-north-1.rds.amazonaws.com; Qdrant URL validated; Redis URL uses TLS; Cerebras provider enforced
- Postgres connectivity ✅: SELECT 1 succeeded
- Qdrant connectivity ✅: HTTP 200
- Redis connectivity ✅: PING succeeded
- API readiness ✅: openapi.json reachable
- Auth token ✅: Received bearer token
- Project upsert ✅: Project exists
- Upload ✅: Chunks=1
- Retrieve ✅: Hits=1
- Staff recommend ✅: candidates=1
- Onboarding generate ❌: 
- Agent query ❌: 
- Skills profile ❌: 
- Audit ❌: 
- GitHub webhook ❌: 

## Triage

- Onboarding generate: see logs
- Agent query: see logs
- Skills profile: see logs
- Audit: see logs
- GitHub webhook: see logs

## Notes

- onboarding failed: HTTP 500
