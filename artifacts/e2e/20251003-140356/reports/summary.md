# E2E Summary

**Run ID:** 20251003-140356  
**Tenant:** tenant1  
**LLM Provider:** cerebras  
**Queue Mode:** redis  
**Draft Mode:** false  

## Results

- OpenAPI readiness: ✅ (code: 200)
- Auth:
  - PO token: ✅
  - BA token: ✅
  - DEV token: ✅
- Project create PX: ⚠️ (code: 409)
- Upload PX.md: ✅ (chunks=3)
- Retrieve (BA): ✅ (hits=2)
- Retrieve (Dev): ✅ (hits=2)
- Agent publish (PO): ❌ (jira_key=n/a, confluence_page_id=n/a)
- Agent publish (Dev): ❌ (expect RBAC denied)
- GitHub webhook: ❌ (worker handled: no)
- Isolation proof: ❌
- Pytest: ❌ (tests=n/a, failures=n/a)

## Key Artifacts

- Responses: `./responses/*.json`
- Logs: `./logs/api.log`, `./logs/worker.log`
- Isolation: `./proof/isolation_report.md`
- Tests: `./reports/junit.xml`, `./reports/coverage.xml`
- Bundle: `./bundle/latest.zip`

## Notes

- agent_po returned 400: expected (200,)
