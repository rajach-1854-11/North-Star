import pytest
from pydantic import ValidationError

from app.schemas.publish import PublishConfluenceRequest, PublishJiraRequest


def test_publish_jira_request_requires_project_reference():
    with pytest.raises(ValidationError) as exc:
        PublishJiraRequest(
            project_key=None,
            project_id=None,
            issue_type="Task",
            summary="North Star task",
        )
    message = str(exc.value)
    assert "project_key or project_id" in message
    assert "TOOL_ARGS_INVALID" in message


def test_publish_jira_request_defaults_epic_name():
    request = PublishJiraRequest(
        project_key="PX",
        project_id=None,
        issue_type="Epic",
        summary="Launch North Star",
        epic_name=None,
    )
    assert request.epic_name == "Launch North Star"


def test_publish_jira_request_subtask_requires_parent():
    with pytest.raises(ValidationError) as exc:
        PublishJiraRequest(
            project_key="PX",
            project_id=None,
            issue_type="Sub-task",
            summary="Follow-up",
            parent_issue_key=None,
        )
    assert "parent_issue_key" in str(exc.value)


def test_publish_confluence_request_requires_space():
    with pytest.raises(ValidationError) as exc:
        PublishConfluenceRequest(space_key=None, space_id=None, title="North Star", body_html="<p>Test</p>")
    assert "space_key or space_id" in str(exc.value)


def test_publish_confluence_request_trims_fields():
    request = PublishConfluenceRequest(space_key=" SPACE ", space_id=None, title="  Title  ", body_html="  <p>Body</p>  ")
    assert request.space_key == "SPACE"
    assert request.title == "Title"
    assert request.body_html == "<p>Body</p>"
