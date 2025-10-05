# Agent Publish Guide

## Overview

North Star's `/agent/query` endpoint lets Admin/PO/BA roles generate a planner-driven execution plan. When the LLM adds `jira_epic` or `confluence_page` steps, the runtime validates arguments, enforces RBAC, and calls Atlassian APIs on behalf of the user. This guide covers the required configuration, request schema, tool-specific constraints, and observable error codes so that product and QA teams can exercise the publish path with confidence.

## Prerequisites

1. **LLM provider** – By default the planner uses Cerebras. You may switch to OpenAI by setting `LLM_PROVIDER=openai` and supplying `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL` (see `.env.example`).
2. **Atlassian credentials** – Populate the following environment variables before starting the API:
   - `ATLASSIAN_BASE_URL`
   - `ATLASSIAN_EMAIL`
   - `ATLASSIAN_API_TOKEN`
   - `ATLASSIAN_CONFLUENCE_SPACE` (default space key)
3. **Draft mode (optional)** – Set `DRAFT_MODE=true` to have Confluence pages created as drafts rather than immediately published.
4. **Role & tenant context** – Requests must include a JWT or explicit dependency that resolves to user claims with `role` (Admin/PO/BA) and `tenant_id`. The `/agent/query` route rejects lower-privilege roles for publish tools.

## Request Contract

```json
{
  "prompt": "Plan work for API redesign",
  "allowed_tools": ["rag_search", "jira_epic", "confluence_page"],
  "targets": ["global"],
  "k": 8,
  "strategy": "qdrant",
  "autonomy": "Ask"
}
```

- `prompt` (string) – Required planner input.
- `allowed_tools` (array of strings) – Optional. Use to prevent publish operations during dry runs.
- `targets`, `k`, `strategy`, `autonomy` – Optional knobs passed to retrieval and planner heuristics.

The response includes the generated plan, any per-step artifacts (including publish responses), and the final planner output. When the LLM service is unavailable, `message` is populated and `output.notes` equals `fallback_heuristic_plan`.

## Publish Tool Requirements

### Jira Epic (`jira_epic`)

The planner must supply:

- `project_key` – Jira project key (validated & resolved to an internal ID).
- `summary` – Epic title.
- `description` – Fully formed text; placeholders such as `${todo}` or `<fill>` are rejected.
- `labels` – Optional list or comma-separated string; normalised at runtime.

Missing or placeholder values trigger a `400` with `code: "TOOL_ARGS_INVALID"` and `details.missing` listing fields to correct.

### Confluence Page (`confluence_page`)

Required arguments:

- `space_key` – Confluence space key.
- `title` – Page title.
- `body_html` – HTML content. If omitted, the planner may provide `evidence` markdown and the system will render it to Confluence HTML.

Pages are created as drafts when `DRAFT_MODE=true`; otherwise they publish immediately. As with Jira, placeholder content results in `TOOL_ARGS_INVALID`.

## Failure Modes & Error Codes

| HTTP Status | Code                      | Meaning                                                                 |
|-------------|--------------------------|-------------------------------------------------------------------------|
| 400         | `TOOL_ARGS_INVALID`      | Planner attempted to publish with missing or placeholder arguments.     |
| 403         | `RBAC_DENIED`            | User role lacks permission for the requested tool.                       |
| 502         | `ATLASSIAN_CONFIG_MISSING` | Environment is missing required Atlassian configuration.               |
| 200         | `error` field in artifact | Upstream Atlassian call failed; see artifact payload for error message. |

When a failure occurs during plan execution, the step's artifact entry records the error payload while later steps continue executing.

## Testing the Flow

1. Ensure the API is running with updated environment variables.
2. POST to `/agent/query` using a token that maps to an Admin/PO/BA user.
3. Confirm the response includes artifacts such as `"step_2:jira_epic"` with Jira-provided IDs.
4. For Confluence drafts, inspect the space's drafts section to verify the page.
5. Run `pytest tests/test_agent_publish.py` to exercise mocked planner publish behaviour.

## Related Automation

- `tests/test_agent_publish.py` covers validation and Atlassian resolver behaviour.
- `tests/test_retriever_router.py` enforces router mode gating.
- `app/scripts/isolation_proof.py` can be invoked for property-based policy regression checks or via the helper scripts `run_isolation_proof.ps1` / `run_isolation_proof.sh` from the repo root.
