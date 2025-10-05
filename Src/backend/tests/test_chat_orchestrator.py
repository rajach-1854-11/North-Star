from __future__ import annotations

import copy

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.agentic.utility import EMPTY_VALUE_SENTINEL
from app.config import settings
from app.domain.schemas import ChatAction, ChatMetadata, ChatMessage, ChatQueryReq, RetrieveHit
from app.services import chat_history
from app.services.chat_orchestrator import ChatOrchestrator


@pytest.fixture
def user_claims() -> dict[str, object]:
    return {
        "tenant_id": settings.tenant_id,
        "role": "PO",
        "accessible_projects": ["PX"],
        "user_id": 101,
    }


def _auth_headers(client: TestClient, username: str = "po_admin") -> dict[str, str]:
    response = client.post(f"/auth/token?username={username}&password=x")
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_chat_orchestrator_low_diversity(
    monkeypatch: pytest.MonkeyPatch,
    client,  # noqa: F841 - ensures app initialises DB
    db_session,
    user_claims: dict[str, object],
) -> None:
    plan_template = {
        "steps": [
            {
                "tool": "rag_search",
                "args": {"query": "help me learn about px", "targets": ["PX"], "k": 12},
            }
        ],
        "output": {"summary": "", "gaps": [], "two_week_plan": [], "notes": ""},
        "_meta": {},
    }

    def fake_register_all_tools() -> None:  # pragma: no cover - trivial monkeypatch
        return None

    def fake_create_plan(task_prompt: str, allowed_tools: list[str] | None = None) -> dict[str, object]:
        assert "help me learn about px" in task_prompt
        return copy.deepcopy(plan_template)

    hit = RetrieveHit(
        text="PX is an enterprise co-pilot for onboarding.",
        score=1.2,
        source="PX",
        chunk_id="chunk-1",
    )

    retrieval_payload = {
        "results": [hit],
        "evidence": "[1] PX snippet",
        "fallback_message": None,
        "rosetta": None,
        "rosetta_narrative_md": None,
    }

    def fake_execute_plan(
        plan: dict[str, object],
        _: dict[str, object],
        **__: object,
    ) -> dict[str, object]:
        return {
            "artifacts": {"step_1:rag_search": retrieval_payload},
            "output": plan.get("output", {}),
        }

    monkeypatch.setattr("app.services.chat_orchestrator.agent_tools.register_all_tools", fake_register_all_tools)
    monkeypatch.setattr("app.services.chat_orchestrator.create_plan", fake_create_plan)
    monkeypatch.setattr("app.services.chat_orchestrator.execute_plan", fake_execute_plan)

    llm_calls: list[list[dict[str, str]]] = []

    def fake_generate_chat_response(messages: list[dict[str, str]], temperature: float = 0.2, max_tokens: int | None = 700) -> str:
        llm_calls.append(messages)
        assert messages[0]["role"] == "system"
        assert "Context passages" in messages[1]["content"]
        return "PX accelerates onboarding by automating project setup."

    monkeypatch.setattr("app.services.chat_orchestrator.generate_chat_response", fake_generate_chat_response)

    orchestrator = ChatOrchestrator(user_claims=user_claims, db=db_session)
    req = ChatQueryReq(prompt="help me learn about px", metadata=ChatMetadata(targets=["PX"]))

    resp = orchestrator.handle(req)

    assert "PX" in resp.reply_md
    assert resp.sources and resp.sources[0]["source"] == "PX"
    assert resp.plan["steps"]
    assert any(action.type == "retrieval" for action in resp.actions)
    assert isinstance(resp.actions[0], ChatAction)
    assert llm_calls, "LLM responder was not invoked"
    assert resp.thread_id > 0

    # ensure messages persisted
    rows = chat_history.list_threads(db_session, tenant_id=user_claims["tenant_id"], user_id=user_claims["user_id"])
    assert rows and rows[0][1] == 2  # user + assistant messages stored


def test_chat_orchestrator_reports_tool_results(
    monkeypatch: pytest.MonkeyPatch,
    client,  # noqa: F841 - ensures app initialises DB
    db_session,
    user_claims: dict[str, object],
) -> None:
    plan_template = {
        "steps": [
            {
                "tool": "rag_search",
                "args": {"query": "create epic", "targets": ["PX"], "k": 12},
            },
            {
                "tool": "jira_epic",
                "args": {"project_key": "PX", "summary": "Create Jira epic for PX onboarding"},
            },
        ],
        "output": {"summary": "Created Jira epic", "gaps": [], "two_week_plan": [], "notes": ""},
        "_meta": {},
    }

    def fake_register_all_tools() -> None:
        return None

    def fake_create_plan(task_prompt: str, allowed_tools: list[str] | None = None) -> dict[str, object]:
        return copy.deepcopy(plan_template)

    hit = RetrieveHit(
        text="PX onboarding uses automated planners.",
        score=1.0,
        source="PX",
        chunk_id="chunk-epic",
    )

    def fake_execute_plan(
        plan: dict[str, object],
        _: dict[str, object],
        **__: object,
    ) -> dict[str, object]:
        return {
            "artifacts": {
                "step_1:rag_search": {"results": [hit], "fallback_message": None, "evidence": None},
                "step_2:jira_epic": {
                    "key": "PX-42",
                    "url": "https://example.atlassian.net/browse/PX-42",
                },
            },
            "output": plan.get("output", {}),
        }

    def fake_generate_chat_response(messages: list[dict[str, str]], temperature: float = 0.2, max_tokens: int | None = 700) -> str:
        return "Automation completed successfully."

    monkeypatch.setattr("app.services.chat_orchestrator.agent_tools.register_all_tools", fake_register_all_tools)
    monkeypatch.setattr("app.services.chat_orchestrator.create_plan", fake_create_plan)
    monkeypatch.setattr("app.services.chat_orchestrator.execute_plan", fake_execute_plan)
    monkeypatch.setattr("app.services.chat_orchestrator.generate_chat_response", fake_generate_chat_response)

    orchestrator = ChatOrchestrator(user_claims=user_claims, db=db_session)
    req = ChatQueryReq(
        prompt="Create a Jira epic for project PX summary='PX onboarding automation' description=\"Automate rituals\"",
        metadata=ChatMetadata(targets=["PX"]),
    )

    resp = orchestrator.handle(req)

    assert "Automation results" in resp.reply_md
    assert "PX-42" in resp.reply_md
    assert "https://example.atlassian.net/browse/PX-42" in resp.reply_md

    rows = chat_history.list_threads(db_session, tenant_id=user_claims["tenant_id"], user_id=user_claims["user_id"])
    assert rows and rows[0][1] == 2


def test_detect_tool_intent_resolves_previous_description(
    db_session,
    user_claims: dict[str, object],
) -> None:
    orchestrator = ChatOrchestrator(user_claims=user_claims, db=db_session)

    history = [
        ChatMessage(role="assistant", content="RBAC enforcement requires updating the permission matrix."),
    ]

    req = ChatQueryReq(
        prompt="Create a Jira epic for project PX. The summary is implement RBAC in PX. Use your previous answer as the description.",
        history=history,
        metadata=ChatMetadata(targets=["PX"]),
    )

    intent = orchestrator._detect_tool_intent(req)

    assert intent.tool == "jira_epic"
    assert intent.summary == "implement RBAC in PX"
    assert intent.description == "RBAC enforcement requires updating the permission matrix."
    assert intent.missing_fields == []


def test_extract_named_value_supports_is_phrasing(db_session, user_claims: dict[str, object]) -> None:
    orchestrator = ChatOrchestrator(user_claims=user_claims, db=db_session)

    value = orchestrator._extract_named_value("The summary is implement RBAC in PX.", "summary")

    assert value == "implement RBAC in PX"


def test_detect_tool_intent_converts_plain_body_to_html(db_session, user_claims: dict[str, object]) -> None:
    orchestrator = ChatOrchestrator(user_claims=user_claims, db=db_session)

    req = ChatQueryReq(
        prompt="Create a Confluence page titled 'PX Weekly Update' space='PX' body='Status update for the week.'",
        metadata=ChatMetadata(),
    )

    intent = orchestrator._detect_tool_intent(req)

    assert intent.tool == "confluence_page"
    assert intent.title == "PX Weekly Update"
    assert intent.space == "PX"
    assert intent.body_html == "<p>Status update for the week.</p>"
    assert intent.missing_fields == []


def test_detect_tool_intent_reuses_previous_answer_for_confluence_body(
    db_session,
    user_claims: dict[str, object],
) -> None:
    orchestrator = ChatOrchestrator(user_claims=user_claims, db=db_session)

    history = [
        ChatMessage(role="assistant", content="PX RBAC requires policy hooks at the adapter boundary."),
    ]

    req = ChatQueryReq(
        prompt="Publish a Confluence page titled 'PX RBAC Notes' space='PX' use your previous answer as the body.",
        history=history,
        metadata=ChatMetadata(additional={"space_key": "PX"}),
    )

    intent = orchestrator._detect_tool_intent(req)

    assert intent.tool == "confluence_page"
    assert intent.title == "PX RBAC Notes"
    assert intent.space == "PX"
    assert intent.body_html is not None and "PX RBAC requires" in intent.body_html
    assert "body_html" not in intent.missing_fields


def test_detect_tool_intent_allows_empty_jira_description(db_session, user_claims: dict[str, object]) -> None:
    orchestrator = ChatOrchestrator(user_claims=user_claims, db=db_session)

    req = ChatQueryReq(
        prompt="Create a Jira epic for project PX summary='PX automation skeleton'. Leave the description blank.",
        metadata=ChatMetadata(targets=["PX"]),
    )

    intent = orchestrator._detect_tool_intent(req)

    assert intent.tool == "jira_epic"
    assert intent.summary == "PX automation skeleton"
    assert intent.description == EMPTY_VALUE_SENTINEL
    assert "description" not in intent.missing_fields


def test_detect_tool_intent_infers_tool_from_field_dump(db_session, user_claims: dict[str, object]) -> None:
    orchestrator = ChatOrchestrator(user_claims=user_claims, db=db_session)

    req = ChatQueryReq(
        prompt="project key is px, summary is kobo, description is bobo. for the user dev_alex",
        metadata=ChatMetadata(),
    )

    intent = orchestrator._detect_tool_intent(req)

    assert intent.tool == "jira_epic"
    assert intent.explicit is True
    assert intent.inferred_project == "PX"
    assert intent.summary == "kobo"
    assert intent.description == "bobo"
    assert intent.missing_fields == []


def test_detect_tool_intent_retries_after_clarification(db_session, user_claims: dict[str, object]) -> None:
    orchestrator = ChatOrchestrator(user_claims=user_claims, db=db_session)

    history = [
        ChatMessage(
            role="assistant",
            content="To create a Jira epic, I need: project key, summary, description.",
            metadata={
                "payload": {
                    "plan": {"_meta": {"clarification_tool": "jira_epic", "pending_retry_tool": "jira_epic"}},
                    "artifacts": {},
                }
            },
        )
    ]

    req = ChatQueryReq(
        prompt="project key is px, summary is implement RBAC in PX.",
        history=history,
        metadata=ChatMetadata(),
    )

    intent = orchestrator._detect_tool_intent(req)

    assert intent.tool == "jira_epic"
    assert intent.explicit is True
    assert intent.inferred_project == "PX"
    assert intent.summary == "implement RBAC in PX"
    assert "description" in intent.missing_fields


def test_chat_orchestrator_blocks_inaccessible_project(
    db_session,
    user_claims: dict[str, object],
) -> None:
    orchestrator = ChatOrchestrator(user_claims=user_claims, db=db_session)

    req = ChatQueryReq(
        prompt="Can you share the roadmap for project PB?",
        metadata=ChatMetadata(targets=["PB"]),
    )

    resp = orchestrator.handle(req)

    assert "access" in resp.reply_md.lower()
    assert resp.plan["_meta"]["denied_projects"] == ["PB"]
    assert resp.actions == []


def test_chat_orchestrator_reports_staffing_recommendation(
    monkeypatch: pytest.MonkeyPatch,
    client,  # noqa: F841 - ensures app initialises DB
    db_session,
    user_claims: dict[str, object],
) -> None:
    plan_template = {
        "steps": [
            {
                "tool": "rag_search",
                "args": {"query": "who can help px", "targets": ["PX"], "k": 12},
            },
            {
                "tool": "staffing_recommend",
                "args": {"project_key": "PX", "include_full": True},
            },
        ],
        "output": {"summary": "", "gaps": [], "two_week_plan": [], "notes": ""},
        "_meta": {},
    }

    def fake_register_all_tools() -> None:
        return None

    def fake_create_plan(task_prompt: str, allowed_tools: list[str] | None = None) -> dict[str, object]:
        return copy.deepcopy(plan_template)

    hit = RetrieveHit(
        text="PX automation requires deep skill engine knowledge.",
        score=0.9,
        source="PX",
        chunk_id="chunk-staffing",
    )

    staffing_payload = {
        "project": {"id": 101, "key": "PX", "name": "PX"},
        "summary": "Top staffing match: Alex Johnson (fit 0.93)",
        "top_candidate": {"developer_id": 7, "developer_name": "Alex Johnson", "fit": 0.93},
        "candidates": [
            {"developer_id": 7, "developer_name": "Alex Johnson", "fit": 0.93},
            {"developer_id": 12, "developer_name": "Taylor Smith", "fit": 0.88},
        ],
        "all_candidates": [
            {"developer_id": 7, "developer_name": "Alex Johnson", "fit": 0.93},
            {"developer_id": 12, "developer_name": "Taylor Smith", "fit": 0.88},
        ],
        "total_candidates": 5,
    }

    def fake_execute_plan(
        plan: dict[str, object],
        _: dict[str, object],
        **__: object,
    ) -> dict[str, object]:
        return {
            "artifacts": {
                "step_1:rag_search": {
                    "results": [hit],
                    "fallback_message": None,
                    "evidence": None,
                },
                "step_2:staffing_recommend": staffing_payload,
            },
            "output": plan.get("output", {}),
        }

    monkeypatch.setattr("app.services.chat_orchestrator.agent_tools.register_all_tools", fake_register_all_tools)
    monkeypatch.setattr("app.services.chat_orchestrator.create_plan", fake_create_plan)
    monkeypatch.setattr("app.services.chat_orchestrator.execute_plan", fake_execute_plan)
    monkeypatch.setattr(
        "app.services.chat_orchestrator.generate_chat_response",
        lambda messages, temperature=0.2, max_tokens=700: "Alex Johnson is the best fit.",
    )

    orchestrator = ChatOrchestrator(user_claims=user_claims, db=db_session)
    req = ChatQueryReq(
        prompt="Who is the developer best suited for project PX?",
        metadata=ChatMetadata(targets=["PX"]),
    )

    resp = orchestrator.handle(req)

    assert "Staffing recommendation" in resp.reply_md
    assert "Staffing recommendation" in resp.reply_md
    assert "Alex Johnson" in resp.reply_md
    assert "Taylor Smith" in resp.reply_md
    assert "fit 0.93" in resp.reply_md


def test_chat_thread_continuation_uses_history(
    monkeypatch: pytest.MonkeyPatch,
    client,  # noqa: F841
    db_session,
    user_claims: dict[str, object],
) -> None:
    plan_template = {
        "steps": [
            {
                "tool": "rag_search",
                "args": {"query": "initial question", "targets": ["PX"], "k": 12},
            }
        ],
        "output": {"summary": "", "gaps": [], "two_week_plan": [], "notes": ""},
        "_meta": {},
    }

    def fake_register_all_tools() -> None:
        return None

    prompt_log: list[str] = []

    def fake_create_plan(task_prompt: str, allowed_tools: list[str] | None = None) -> dict[str, object]:
        prompt_log.append(task_prompt)
        return copy.deepcopy(plan_template)

    hit = RetrieveHit(text="PX answer", score=1.0, source="PX", chunk_id="chunk-1")

    def fake_execute_plan(
        plan: dict[str, object],
        _: dict[str, object],
        **__: object,
    ) -> dict[str, object]:
        return {
            "artifacts": {"step_1:rag_search": {"results": [hit], "fallback_message": None, "evidence": None}},
            "output": plan.get("output", {}),
        }

    def fake_generate_chat_response(messages: list[dict[str, str]], temperature: float = 0.2, max_tokens: int | None = 700) -> str:
        return "First reply" if len(prompt_log) == 1 else "Follow-up reply"

    monkeypatch.setattr("app.services.chat_orchestrator.agent_tools.register_all_tools", fake_register_all_tools)
    monkeypatch.setattr("app.services.chat_orchestrator.create_plan", fake_create_plan)
    monkeypatch.setattr("app.services.chat_orchestrator.execute_plan", fake_execute_plan)
    monkeypatch.setattr("app.services.chat_orchestrator.generate_chat_response", fake_generate_chat_response)

    orchestrator = ChatOrchestrator(user_claims=user_claims, db=db_session)

    first_req = ChatQueryReq(prompt="initial question", metadata=ChatMetadata(targets=["PX"]))
    first_resp = orchestrator.handle(first_req)

    follow_req = ChatQueryReq(prompt="what else?", metadata=ChatMetadata(targets=["PX"]), thread_id=first_resp.thread_id)
    follow_resp = orchestrator.handle(follow_req)

    assert follow_resp.thread_id == first_resp.thread_id
    assert len(prompt_log) == 2
    assert "User: initial question" in prompt_log[1]
    assert "Assistant:" in prompt_log[1]

    rows = chat_history.list_threads(db_session, tenant_id=user_claims["tenant_id"], user_id=user_claims["user_id"])
    assert rows and rows[0][1] == 4  # two turns = four messages

def test_chat_thread_endpoints(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    plan_template = {
        "steps": [
            {"tool": "rag_search", "args": {"query": "hello", "targets": ["PX"], "k": 12}},
        ],
        "output": {"summary": "", "gaps": [], "two_week_plan": [], "notes": ""},
        "_meta": {},
    }

    def fake_register_all_tools() -> None:
        return None

    def fake_create_plan(task_prompt: str, allowed_tools: list[str] | None = None) -> dict[str, object]:
        return copy.deepcopy(plan_template)

    hit = RetrieveHit(text="PX detail", score=0.9, source="PX", chunk_id="chunk-42")

    def fake_execute_plan(
        plan: dict[str, object],
        user_claims: dict[str, object],
        **__: object,
    ) -> dict[str, object]:
        return {
            "artifacts": {
                "step_1:rag_search": {
                    "results": [hit],
                    "fallback_message": None,
                    "evidence": None,
                }
            },
            "output": plan.get("output", {}),
        }

    def fake_generate_chat_response(messages: list[dict[str, str]], temperature: float = 0.2, max_tokens: int | None = 700) -> str:
        return "Thread reply"

    monkeypatch.setattr("app.services.chat_orchestrator.agent_tools.register_all_tools", fake_register_all_tools)
    monkeypatch.setattr("app.services.chat_orchestrator.create_plan", fake_create_plan)
    monkeypatch.setattr("app.services.chat_orchestrator.execute_plan", fake_execute_plan)
    monkeypatch.setattr("app.services.chat_orchestrator.generate_chat_response", fake_generate_chat_response)

    headers = _auth_headers(client)

    create_resp = client.post("/chat/threads", json={"title": "Demo thread"}, headers=headers)
    assert create_resp.status_code == 200, create_resp.text
    thread_id = create_resp.json()["id"]

    chat_payload = {
        "prompt": "hello",
        "metadata": {"targets": ["PX"]},
        "thread_id": thread_id,
    }
    first = client.post("/chat/session", json=chat_payload, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["thread_id"] == thread_id

    follow_payload = {
        "prompt": "any updates?",
        "metadata": {"targets": ["PX"]},
        "thread_id": thread_id,
    }
    second = client.post("/chat/session", json=follow_payload, headers=headers)
    assert second.status_code == 200, second.text
    assert second.json()["thread_id"] == thread_id

    list_resp = client.get("/chat/threads", headers=headers)
    assert list_resp.status_code == 200, list_resp.text
    threads = list_resp.json()["threads"]
    assert threads and threads[0]["message_count"] == 4
    assert threads[0]["last_message_at"] is not None

    detail_resp = client.get(f"/chat/threads/{thread_id}", headers=headers)
    assert detail_resp.status_code == 200, detail_resp.text
    body = detail_resp.json()
    assert body["message_count"] == 4
    assert len(body["messages"]) == 4
    assert body["messages"][0]["content"].startswith("hello")
    assert body["messages"][0]["timestamp"] is not None

    history_resp = client.get(f"/chat/threads/{thread_id}/messages", headers=headers)
    assert history_resp.status_code == 200, history_resp.text
    assert history_resp.json()["message_count"] == 4

    patch_resp = client.patch(
        f"/chat/threads/{thread_id}",
        json={"title": "Renamed thread"},
        headers=headers,
    )
    assert patch_resp.status_code == 200, patch_resp.text
    patched = patch_resp.json()
    assert patched["title"] == "Renamed thread"
    assert patched["message_count"] == 4

    delete_resp = client.delete(f"/chat/threads/{thread_id}", headers=headers)
    assert delete_resp.status_code == 204, delete_resp.text

    missing_resp = client.get(f"/chat/threads/{thread_id}", headers=headers)
    assert missing_resp.status_code == 404, missing_resp.text

    remaining = client.get("/chat/threads", headers=headers)
    assert remaining.status_code == 200, remaining.text
    assert remaining.json()["threads"] == []


def test_execute_plan_respects_default_consent(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ports import planner

    fake_registry: dict[str, object] = {}

    def fake_tool(*, user_claims: dict[str, object], **kwargs: object) -> dict[str, object]:
        return {"ok": True, "args": kwargs}

    fake_registry["confluence_page"] = fake_tool

    monkeypatch.setattr(planner, "_TOOL_REGISTRY", fake_registry)
    monkeypatch.setattr(planner, "enforce", lambda tool, role: None)
    monkeypatch.setattr(planner.audit_log, "write_chat_audit_entry", lambda **_: None)

    user_claims = {"role": "PO", "tenant_id": "tenant1", "user_id": 1}
    plan = {
        "steps": [
            {
                "tool": "confluence_page",
                "args": {"space_key": "PX", "title": "Doc", "body_html": "<p>Doc</p>"},
            }
        ],
        "output": {},
        "_meta": {"allowed_tools": ["confluence_page"], "allowed_tools_provided": False},
    }

    result = planner.execute_plan(plan, user_claims)
    assert result["artifacts"]["step_1:confluence_page"]["ok"] is True


def test_execute_plan_respects_aliases_in_explicit_consent(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ports import planner

    fake_registry: dict[str, object] = {}

    def fake_tool(*, user_claims: dict[str, object], **kwargs: object) -> dict[str, object]:
        return {"ok": True}

    fake_registry["confluence_page"] = fake_tool

    monkeypatch.setattr(planner, "_TOOL_REGISTRY", fake_registry)
    monkeypatch.setattr(planner, "enforce", lambda tool, role: None)
    monkeypatch.setattr(planner.audit_log, "write_chat_audit_entry", lambda **_: None)

    user_claims = {"role": "PO", "tenant_id": "tenant1", "user_id": 1}
    plan = {
        "steps": [
            {
                "tool": "confluence_page",
                "args": {"space_key": "PX", "title": "Doc", "body_html": "<p>Body</p>"},
            }
        ],
        "output": {},
        "_meta": {"allowed_tools": ["confluence_page"], "allowed_tools_provided": True},
    }

    result = planner.execute_plan(plan, user_claims)
    assert result["artifacts"]["step_1:confluence_page"]["ok"] is True


def test_chat_orchestrator_blocks_unapproved_tool_steps(
    monkeypatch: pytest.MonkeyPatch,
    db_session,
    user_claims: dict[str, object],
) -> None:
    plan_template = {
        "steps": [
            {
                "tool": "rag_search",
                "args": {"query": "How does PX work?", "targets": ["PX"], "k": 12},
            },
            {
                "tool": "jira_epic",
                "args": {},
            },
        ],
        "output": {"summary": "", "gaps": [], "two_week_plan": [], "notes": ""},
        "_meta": {},
    }

    def fake_register_all_tools() -> None:
        return None

    llm_calls: list[list[dict[str, str]]] = []

    def fake_create_plan(task_prompt: str, allowed_tools: list[str] | None = None) -> dict[str, object]:
        assert allowed_tools == ["rag_search"], allowed_tools
        return copy.deepcopy(plan_template)

    hit = RetrieveHit(text="PX knowledge", score=0.8, source="PX", chunk_id="chunk-px")

    def fake_execute_plan(plan: dict[str, object], _: dict[str, object], **__: object) -> dict[str, object]:
        assert [step.get("tool") for step in plan.get("steps", [])] == ["rag_search"]
        return {
            "artifacts": {
                "step_1:rag_search": {
                    "results": [hit],
                    "fallback_message": None,
                    "evidence": "[1] PX knowledge",
                }
            },
            "output": plan.get("output", {}),
        }

    def fake_generate_chat_response(messages: list[dict[str, str]], temperature: float = 0.2, max_tokens: int | None = 700) -> str:
        llm_calls.append(messages)
        return "PX automates onboarding workflows."

    monkeypatch.setattr("app.services.chat_orchestrator.agent_tools.register_all_tools", fake_register_all_tools)
    monkeypatch.setattr("app.services.chat_orchestrator.create_plan", fake_create_plan)
    monkeypatch.setattr("app.services.chat_orchestrator.execute_plan", fake_execute_plan)
    monkeypatch.setattr("app.services.chat_orchestrator.generate_chat_response", fake_generate_chat_response)

    orchestrator = ChatOrchestrator(user_claims=user_claims, db=db_session)
    req = ChatQueryReq(prompt="How does PX onboarding work?", metadata=ChatMetadata(targets=["PX"]))

    resp = orchestrator.handle(req)

    assert llm_calls, "Expected LLM response to be generated"
    assert all(step["tool"] == "rag_search" for step in resp.plan["steps"])
    assert resp.artifacts.get("step_1:rag_search")


def test_chat_orchestrator_enriches_plan_for_explicit_tool(
    monkeypatch: pytest.MonkeyPatch,
    db_session,
    user_claims: dict[str, object],
) -> None:
    plan_template = {
        "steps": [
            {
                "tool": "rag_search",
                "args": {"query": "", "targets": ["PX"], "k": 12},
            },
            {
                "tool": "jira_epic",
                "args": {},
            },
        ],
        "output": {"summary": "Created Jira epic", "gaps": [], "two_week_plan": [], "notes": ""},
        "_meta": {},
    }

    def fake_register_all_tools() -> None:
        return None

    captured_plan: dict[str, object] = {}

    def fake_create_plan(task_prompt: str, allowed_tools: list[str] | None = None) -> dict[str, object]:
        assert set(allowed_tools or []) == {"rag_search", "jira_epic"}
        return copy.deepcopy(plan_template)

    def fake_execute_plan(plan: dict[str, object], _: dict[str, object], **__: object) -> dict[str, object]:
        captured_plan["plan"] = copy.deepcopy(plan)
        return {
            "artifacts": {
                "step_1:rag_search": {"results": [], "fallback_message": None, "evidence": None},
                "step_2:jira_epic": {"key": "PX-101", "url": "https://jira/pX-101"},
            },
            "output": plan.get("output", {}),
        }

    def fake_generate_chat_response(messages: list[dict[str, str]], temperature: float = 0.2, max_tokens: int | None = 700) -> str:
        return "Created the Jira epic with the supplied details."

    monkeypatch.setattr("app.services.chat_orchestrator.agent_tools.register_all_tools", fake_register_all_tools)
    monkeypatch.setattr("app.services.chat_orchestrator.create_plan", fake_create_plan)
    monkeypatch.setattr("app.services.chat_orchestrator.execute_plan", fake_execute_plan)
    monkeypatch.setattr("app.services.chat_orchestrator.generate_chat_response", fake_generate_chat_response)

    orchestrator = ChatOrchestrator(user_claims=user_claims, db=db_session)
    req = ChatQueryReq(
        prompt="Create a Jira epic in project PX summary='PX automation' description='Automate onboarding flows'",
        metadata=ChatMetadata(targets=["PX"]),
    )

    resp = orchestrator.handle(req)

    jira_step = next(step for step in resp.plan["steps"] if step["tool"] != "rag_search")
    assert jira_step["args"]["project_key"] == "PX"
    assert jira_step["args"]["summary"] == "PX automation"
    assert jira_step["args"]["description"] == "Automate onboarding flows"
    assert resp.plan["_meta"].get("project_key") == "PX"
    assert captured_plan["plan"]["steps"][1]["args"]["project_key"] == "PX"
    assert resp.artifacts["step_2:jira_epic"]["key"] == "PX-101"


def test_chat_orchestrator_clarifies_missing_intent_fields_before_planning(
    monkeypatch: pytest.MonkeyPatch,
    db_session,
    user_claims: dict[str, object],
) -> None:
    def fake_register_all_tools() -> None:
        return None

    create_called = False

    def fake_create_plan(task_prompt: str, allowed_tools: list[str] | None = None) -> dict[str, object]:
        nonlocal create_called
        create_called = True
        return {}

    def fake_execute_plan(plan: dict[str, object], _: dict[str, object], **__: object) -> dict[str, object]:
        raise AssertionError("execute_plan should not be invoked when prompting for clarifications")

    monkeypatch.setattr("app.services.chat_orchestrator.agent_tools.register_all_tools", fake_register_all_tools)
    monkeypatch.setattr("app.services.chat_orchestrator.create_plan", fake_create_plan)
    monkeypatch.setattr("app.services.chat_orchestrator.execute_plan", fake_execute_plan)

    orchestrator = ChatOrchestrator(user_claims=user_claims, db=db_session)
    req = ChatQueryReq(prompt="Can you create a Jira epic?", metadata=ChatMetadata(targets=["PX"]))

    resp = orchestrator.handle(req)

    assert create_called is False
    assert resp.pending_fields == {"tool": "jira_epic", "missing": ["summary", "description"]}
    assert "Jira epic" in resp.reply_md
    assert resp.plan["_meta"].get("clarification_tool") == "jira_epic"


def test_chat_orchestrator_prompts_for_missing_tool_fields(
    monkeypatch: pytest.MonkeyPatch,
    db_session,
    user_claims: dict[str, object],
) -> None:
    plan_template = {
        "steps": [
            {
                "tool": "jira_issue",
                "args": {"project_key": "PX"},
            }
        ],
        "output": {"summary": "", "gaps": [], "two_week_plan": [], "notes": ""},
        "_meta": {},
    }

    def fake_register_all_tools() -> None:
        return None

    def fake_create_plan(task_prompt: str, allowed_tools: list[str] | None = None) -> dict[str, object]:
        return copy.deepcopy(plan_template)

    def fake_execute_plan(
        plan: dict[str, object],
        user_claims: dict[str, object],
        **__: object,
    ) -> dict[str, object]:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "TOOL_ARGS_INVALID",
                "message": "Jira issue requires additional fields",
                "details": {"missing": ["summary", "description"]},
            },
        )

    monkeypatch.setattr("app.services.chat_orchestrator.agent_tools.register_all_tools", fake_register_all_tools)
    monkeypatch.setattr("app.services.chat_orchestrator.create_plan", fake_create_plan)
    monkeypatch.setattr("app.services.chat_orchestrator.execute_plan", fake_execute_plan)

    orchestrator = ChatOrchestrator(user_claims=user_claims, db=db_session)
    req = ChatQueryReq(
        prompt="create jira issue in project PX summary='Launch PX onboarding' description='Need story outline'",
        metadata=ChatMetadata(targets=["PX"]),
    )

    resp = orchestrator.handle(req)

    assert resp.pending_fields == {
        "code": "TOOL_ARGS_INVALID",
        "missing": ["summary", "description"],
        "message": "Jira issue requires additional fields",
    }
    assert "Need a bit more info" in resp.reply_md
    assert "summary" in resp.reply_md
    assert resp.thread_id > 0

    threads = chat_history.list_threads(
        db_session,
        tenant_id=user_claims["tenant_id"],
        user_id=user_claims["user_id"],
    )
    assert threads and threads[0][1] == 2