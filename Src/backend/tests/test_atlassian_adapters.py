import httpx
import pytest

from fastapi import HTTPException

from app.adapters import confluence_adapter, jira_adapter
from app.schemas.publish import PublishJiraRequest


class _DummyClient:
    def __init__(self, *, get_response=None, post_response=None):
        self._get_response = get_response
        self._post_response = post_response
        self.last_request = None
        self.last_json = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url, headers=None, params=None):
        self.last_request = {"method": "GET", "url": url, "params": params}
        return self._get_response(url, headers=headers, params=params)

    def post(self, url, headers=None, json=None):
        self.last_request = {"method": "POST", "url": url, "json": json}
        self.last_json = json
        return self._post_response(url, headers=headers, json=json)


def _success_response(json_payload, status_code: int = 200):
    class _Resp:
        def __init__(self):
            self.status_code = status_code

        def raise_for_status(self):
            return None

        def json(self):
            return json_payload

    return _Resp()


def _error_response(status_code: int, body: str):
    request = httpx.Request("POST", "https://example.test")
    response = httpx.Response(status_code=status_code, text=body, request=request)

    class _Resp:
        def raise_for_status(self):
            raise httpx.HTTPStatusError("error", request=request, response=response)

    return _Resp()


def test_jira_task_ok(monkeypatch):
    captured = {}

    def _post_response(url, headers=None, json=None):
        captured["url"] = url
        captured["payload"] = json
        return _success_response({"key": "PX-100"}, status_code=201)

    dummy = _DummyClient(post_response=_post_response)
    monkeypatch.setattr(jira_adapter, "sync_client", lambda timeout=60: dummy)
    monkeypatch.setattr(jira_adapter, "_epic_name_allowed_on_create", lambda *_, **__: True)

    request = PublishJiraRequest(
        project_key="PX",
        project_id="10001",
        issue_type="Task",
        summary="Hybrid retriever runbook",
        description_text="generated",
    )

    result = jira_adapter.create_issue(request=request, description_adf=None, labels=None)

    assert result["key"] == "PX-100"
    assert captured["url"].endswith("/rest/api/3/issue")
    fields = captured["payload"]["fields"]
    assert fields["project"] == {"id": "10001"}
    assert fields["issuetype"] == {"name": "Task"}
    assert "Epic Name" not in fields


def test_jira_epic_ok(monkeypatch):
    captured = {}

    def _post_response(url, headers=None, json=None):
        captured["url"] = url
        captured["payload"] = json
        return _success_response({"key": "PX-999"}, status_code=201)

    dummy = _DummyClient(post_response=_post_response)
    monkeypatch.setattr(jira_adapter, "sync_client", lambda timeout=60: dummy)
    monkeypatch.setattr(jira_adapter, "_epic_name_allowed_on_create", lambda *_, **__: True)

    request = PublishJiraRequest(
        project_key="PX",
        project_id="10001",
        issue_type="Epic",
        summary="North Star smoke epic",
        description_text="generated",
        epic_name="North Star smoke epic",
    )

    result = jira_adapter.create_issue(
        request=request,
        description_adf={
            "type": "doc",
            "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": "generated"}]}],
        },
        labels=["northstar"],
        epic_name_field_id="customfield_10011",
    )

    assert result["key"] == "PX-999"
    assert captured["url"].endswith("/rest/api/3/issue")
    fields = captured["payload"]["fields"]
    assert fields["project"] == {"id": "10001"}
    assert fields["issuetype"] == {"name": "Epic"}
    assert fields["customfield_10011"] == "North Star smoke epic"
    assert fields["labels"] == ["northstar"]
    assert fields["description"]["type"] == "doc"


def test_jira_create_issue_raises_tool_args_for_400(monkeypatch):
    def _post_response(url, headers=None, json=None):
        return _error_response(400, "Epic Name missing")

    dummy = _DummyClient(post_response=_post_response)
    monkeypatch.setattr(jira_adapter, "sync_client", lambda timeout=60: dummy)
    monkeypatch.setattr(jira_adapter, "_epic_name_allowed_on_create", lambda *_, **__: True)

    request = PublishJiraRequest(
        project_key="PX",
        project_id="10001",
        issue_type="Epic",
        summary="Missing epic name",
    )

    with pytest.raises(HTTPException) as exc:
        jira_adapter.create_issue(request=request, epic_name_field_id="customfield_10011")

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "UPSTREAM_VALIDATION"


def test_confluence_page_ok_v1(monkeypatch):
    captured = {}

    def _get_response(url, headers=None, params=None):
        assert params == {"keys": "SPACE"}
        return _success_response({"results": [{"id": "42", "key": "SPACE", "name": "Space"}]})

    def _post_response(url, headers=None, json=None):
        captured["json"] = json
        return _success_response({"id": "111", "_links": {"webui": "/wiki/webui"}}, status_code=201)

    dummy = _DummyClient(get_response=_get_response, post_response=_post_response)
    monkeypatch.setattr(confluence_adapter, "sync_client", lambda timeout=60: dummy)

    result = confluence_adapter.create_page(
        space_id="42",
        space_key="SPACE",
        title="North Star onboarding",
        body_html="<p>hello</p>",
        draft=False,
    )

    assert result["page_id"] == "111"
    assert result["_links"]["webui"] == "/wiki/webui"
    assert captured["json"]["spaceId"] == "42"
    assert captured["json"]["body"]["representation"] == "storage"


def test_confluence_page_ok_v2(monkeypatch):
    captured = {}

    def _post_response(url, headers=None, json=None):
        captured["json"] = json
        return _success_response({"id": "222", "_links": {"webui": "/wiki/x"}}, status_code=200)

    dummy = _DummyClient(post_response=_post_response)
    monkeypatch.setattr(confluence_adapter, "sync_client", lambda timeout=60: dummy)

    result = confluence_adapter.create_page(
        space_id="99",
        space_key="SPACE",
        title="North Star onboarding",
        body_html="<p>hello</p>",
        draft=True,
    )

    assert result["status"] == "draft"
    assert result["_links"]["webui"] == "/wiki/x"
    assert captured["json"]["spaceId"] == "99"


def test_confluence_space_missing_inputs_raise_tool_args():
    with pytest.raises(HTTPException) as exc:
        confluence_adapter.resolve_space()

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "TOOL_ARGS_INVALID"
