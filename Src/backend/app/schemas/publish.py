"""Schemas for artifact publishing flows."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

IssueType = Literal["Task", "Story", "Bug", "Epic", "Sub-task"]


class PublishJiraRequest(BaseModel):
    project_key: Optional[str] = Field(default=None, description="Jira project key, e.g., PX")
    project_id: Optional[str] = Field(default=None, description="Jira project id, e.g., 10002")
    issue_type: IssueType
    summary: str
    description_text: Optional[str] = None
    epic_name: Optional[str] = None
    parent_issue_key: Optional[str] = None

    @field_validator("project_key", "project_id", "description_text", "epic_name", "parent_issue_key", mode="before")
    @classmethod
    def _strip_optionals(cls, value):
        if value is None:
            return None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("summary", mode="before")
    @classmethod
    def _strip_summary(cls, value: str) -> str:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = str(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("TOOL_ARGS_INVALID: summary required")
            return stripped
        raise ValueError("TOOL_ARGS_INVALID: summary required")

    @model_validator(mode="after")
    def _validate(self) -> "PublishJiraRequest":
        if not self.project_key and not self.project_id:
            raise ValueError("TOOL_ARGS_INVALID: project_key or project_id required")
        if self.issue_type == "Sub-task" and not self.parent_issue_key:
            raise ValueError("TOOL_ARGS_INVALID: parent_issue_key required for Sub-task")
        if self.issue_type == "Epic" and not self.epic_name:
            self.epic_name = self.summary
        return self


class PublishConfluenceRequest(BaseModel):
    space_key: Optional[str] = None
    space_id: Optional[str] = None
    title: str
    body_html: Optional[str] = None

    @field_validator("space_key", "space_id", "body_html", mode="before")
    @classmethod
    def _strip_optional_fields(cls, value):
        if value is None:
            return None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title(cls, value: str) -> str:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = str(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("TOOL_ARGS_INVALID: title required")
            return stripped
        raise ValueError("TOOL_ARGS_INVALID: title required")

    @model_validator(mode="after")
    def _validate(self) -> "PublishConfluenceRequest":
        if not self.space_key and not self.space_id:
            raise ValueError("TOOL_ARGS_INVALID: space_key or space_id required")
        return self
