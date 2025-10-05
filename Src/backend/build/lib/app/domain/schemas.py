"""Pydantic schemas for API requests and responses."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

RetrievalStrategy = Literal["qdrant", "rrf"]
AutonomyMode = Literal["Ask", "Auto", "Manual", "Tell"]


class TokenResp(BaseModel):
    """OAuth-style token response returned during authentication."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = 3600


class RetrieveReq(BaseModel):
    """Request payload for retrieval endpoints."""

    query: str
    targets: List[str] = Field(default_factory=list)
    k: int = 12
    lambda_weight: float = 0.6
    strategy: RetrievalStrategy = "qdrant"
    include_rosetta: bool = False
    known_projects: List[str] = Field(default_factory=list)


class RetrieveHit(BaseModel):
    """Individual retrieval hit containing text and metadata."""

    text: str
    score: float
    source: str
    chunk_id: str


class RetrieveResp(BaseModel):
    """Response wrapper for retrieval results."""

    results: List[RetrieveHit]
    message: str | None = None
    rosetta: Dict[str, Any] | None = None
    rosetta_narrative_md: str | None = None


class ProjectResp(BaseModel):
    """Project representation used for create and read operations."""

    id: int
    key: str
    name: str
    description: Optional[str] = None


class UserResp(BaseModel):
    """Lightweight projection of a platform user."""

    id: int
    username: str
    role: str
    tenant_id: str


class UserListResp(BaseModel):
    """Collection wrapper for user listings."""

    users: List[UserResp]


class UserRolePatchReq(BaseModel):
    """Request body for updating a user's role."""

    role: Literal["Admin", "PO", "BA", "Dev"]


class AssignmentCreateReq(BaseModel):
    """Request body for assignment creation."""

    developer_id: int
    project_id: int
    role: Optional[str] = None
    start_date: Optional[date] = None


class AssignmentUpdateReq(BaseModel):
    """Request body for updating an existing assignment."""

    role: Optional[str] = None
    status: Optional[str] = None
    end_date: Optional[date] = None


class AssignmentResp(BaseModel):
    """Assignment projection returned from admin endpoints."""

    id: int
    developer_id: int
    project_id: int
    role: Optional[str] = None
    status: str


class AssignmentListResp(BaseModel):
    """Wrapper for assignment listings."""

    assignments: List[AssignmentResp]


class UploadResp(BaseModel):
    """Response payload for document ingestion."""

    project_key: str
    collection: str
    count: int
    chunks: int
    message: str | None = None


class AuditEntry(BaseModel):
    """Single audit log entry."""

    ts: datetime
    actor: int
    action: str
    status: int
    request_id: str


class AuditResp(BaseModel):
    """Audit log response wrapper."""

    items: List[AuditEntry]


class SkillEntry(BaseModel):
    """Single skill row for a developer."""

    path: str
    score: float
    last_seen: datetime | None


class SkillProfileResp(BaseModel):
    """Developer skill profile response."""

    developer_id: int
    skills: List[SkillEntry]


class StaffCandidate(BaseModel):
    """Staffing candidate with fit breakdown information."""

    developer_id: int
    fit: float
    factors: Dict[str, float]
    availability: Dict[str, Any]
    explanations: List[str]


class StaffResp(BaseModel):
    """Response payload for staffing results."""

    project_id: int
    candidates: List[StaffCandidate]


class OnboardingReq(BaseModel):
    """Request body for onboarding plan generation."""

    developer_id: int
    project_id: int
    autonomy: AutonomyMode = "Ask"


class Artifact(BaseModel):
    """Reference to generated planner artifacts."""

    key: str | None = None
    url: str | None = None
    page_id: str | None = None


class OnboardingPlan(BaseModel):
    """Structured onboarding plan output."""

    summary: str
    gaps: List[Dict[str, Any]]
    two_week_plan: List[Dict[str, Any]]
    artifacts: Dict[str, Artifact]
    notice: str | None = None


class OnboardingResp(BaseModel):
    """Response wrapper for onboarding plan generation."""

    plan: OnboardingPlan
    audit_ref: str
    message: str | None = None


class AgentQueryReq(BaseModel):
    """Request payload for the agent planning endpoint."""

    prompt: str
    allowed_tools: List[str] = Field(default_factory=lambda: ["rag_search", "jira_epic", "confluence_page"])
    targets: List[str] = Field(default_factory=list)
    k: int = 12
    strategy: RetrievalStrategy = "qdrant"
    autonomy: AutonomyMode = "Ask"
    tool_overrides: Dict[str, Any] | None = None


class AgentQueryResp(BaseModel):
    """Response payload for the agent planning endpoint."""

    plan: Dict[str, Any]
    artifacts: Dict[str, Any]
    output: Dict[str, Any]
    message: str | None = None


class ChatMessage(BaseModel):
    """Single turn in a chat conversation."""

    role: Literal["user", "assistant", "system"]
    content: str


class ChatMetadata(BaseModel):
    """Optional metadata shared by the frontend to guide tool selection."""

    intent: Optional[str] = None
    targets: List[str] = Field(default_factory=list)
    include_rosetta: Optional[bool] = None
    known_projects: List[str] = Field(default_factory=list)
    additional: Dict[str, Any] = Field(default_factory=dict)


class ChatQueryReq(BaseModel):
    """Request payload for the unified chat endpoint."""

    prompt: str
    autonomy: AutonomyMode = "Ask"
    history: List[ChatMessage] = Field(default_factory=list)
    allowed_tools: Optional[List[str]] = None
    metadata: Optional[ChatMetadata] = None


class ChatAction(BaseModel):
    """Action that was executed as part of the chat turn."""

    type: Literal["jira_ticket", "confluence_page", "retrieval", "info"]
    payload: Dict[str, Any] = Field(default_factory=dict)


class ChatResp(BaseModel):
    """Response payload returned by the chat endpoint."""

    reply_md: str
    plan: Dict[str, Any]
    artifacts: Dict[str, Any]
    output: Dict[str, Any]
    actions: List[ChatAction] = Field(default_factory=list)
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    two_week_plan: List[Dict[str, Any]] = Field(default_factory=list)
    pending_fields: Dict[str, Any] | None = None
    message: str | None = None
