"""Pydantic schemas for API requests and responses."""

from __future__ import annotations

from typing import Any, Dict, List, Literal

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


class RetrieveHit(BaseModel):
    """Individual retrieval hit containing text and metadata."""

    text: str
    score: float
    source: str
    chunk_id: str


class RetrieveResp(BaseModel):
    """Response wrapper for retrieval results."""

    results: List[RetrieveHit]


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


class OnboardingResp(BaseModel):
    """Response wrapper for onboarding plan generation."""

    plan: OnboardingPlan
    audit_ref: str


class AgentQueryReq(BaseModel):
    """Request payload for the agent planning endpoint."""

    prompt: str
    allowed_tools: List[str] = Field(default_factory=lambda: ["rag_search", "jira_epic", "confluence_page"])
    targets: List[str] = Field(default_factory=list)
    k: int = 12
    strategy: RetrievalStrategy = "qdrant"
    autonomy: AutonomyMode = "Ask"


class AgentQueryResp(BaseModel):
    """Response payload for the agent planning endpoint."""

    plan: Dict[str, Any]
    artifacts: Dict[str, Any]
    output: Dict[str, Any]
