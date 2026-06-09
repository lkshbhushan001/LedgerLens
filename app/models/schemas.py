"""Pydantic domain models shared across the application.

These models enforce the contracts for documents, chunks, users, RBAC metadata,
and API request/response payloads. Every service downstream depends on them.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class DocumentType(str, Enum):
    PDF = "pdf"
    XLSX = "xlsx"
    CSV = "csv"
    PNG = "png"
    JPG = "jpg"
    MD = "markdown"


class ChunkType(str, Enum):
    TEXT = "text"
    TABLE = "table"
    IMAGE_DESCRIPTION = "image_description"


# ---------------------------------------------------------------------------
# RBAC & Identity
# ---------------------------------------------------------------------------

class RBACMetadata(BaseModel):
    """Mathematical access-control payload attached to every chunk.

    The enforcement rule at retrieval time is:
        metadata.allowed_roles ∩ user.permission_groups != ∅
    """

    allowed_roles: list[str] = Field(..., min_length=1)
    document_id: str
    source_filename: str
    uploaded_by: str
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    doc_type: DocumentType
    chunk_type: ChunkType = ChunkType.TEXT
    # Optional fine-grained classification for financial domain
    fund_family: str | None = None
    report_period: str | None = None  # e.g. "2024-Q3"

    @field_validator("allowed_roles")
    @classmethod
    def _roles_lowercase(cls, v: list[str]) -> list[str]:
        return [r.lower().strip() for r in v]


class UserIdentity(BaseModel):
    """Resolved user after JWT validation."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: str
    email: str
    permission_groups: list[str] = Field(alias="roles")
    is_admin: bool = False

    def can_access(self, metadata: RBACMetadata) -> bool:
        """Evaluate the RBAC intersection condition."""
        if self.is_admin:
            return True
        user_perms = {p.lower() for p in self.permission_groups}
        doc_roles = {r.lower() for r in metadata.allowed_roles}
        return not user_perms.isdisjoint(doc_roles)


# ---------------------------------------------------------------------------
# Document & Chunk
# ---------------------------------------------------------------------------

class DocumentIngestRequest(BaseModel):
    """Payload for initiating document ingestion."""

    source_filename: str = Field(..., min_length=1)
    doc_type: DocumentType
    allowed_roles: list[str] = Field(..., min_length=1)
    fund_family: str | None = None
    report_period: str | None = None
    # Raw file bytes uploaded via multipart; this model carries metadata only
    extra_metadata: dict[str, Any] = Field(default_factory=dict)


class ChunkPayload(BaseModel):
    """A single chunk ready for embedding and vector insertion."""

    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str = Field(..., min_length=1)
    embedding: list[float] | None = None
    sparse_embedding: dict[str, list] | None = None  # <-- ADD THIS LINE
    token_count: int | None = None
    chunk_type: ChunkType = ChunkType.TEXT
    rbac: RBACMetadata
    page_number: int | None = None
    # For image chunks: the generated description from vision LLM
    image_description: str | None = None


class DocumentRecord(BaseModel):
    """Stored document header (not chunks)."""

    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_filename: str
    doc_type: DocumentType
    rbac: RBACMetadata
    chunk_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processing_status: str = "pending"  # pending | processing | completed | failed


# ---------------------------------------------------------------------------
# Query & Retrieval
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    """Incoming user query."""

    question: str = Field(..., min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20)
    # Optional: restrict search to specific document(s)
    filter_document_ids: list[str] | None = None


class RetrievedChunk(BaseModel):
    """Chunk returned from the retrieval layer."""

    chunk_id: str
    text: str
    score: float
    chunk_type: ChunkType
    rbac: RBACMetadata
    page_number: int | None = None


class RAGResponse(BaseModel):
    """Final API response to the user."""

    answer: str
    sources: list[RetrievedChunk]
    latency_ms: float
    cache_hit: bool = False
    guardrail_passed: bool = True
    evaluation_score: dict[str, float] | None = None


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

class EvaluationResult(BaseModel):
    """Offline evaluation metrics (Ragas-style)."""

    context_relevance: float  # Retrieved Relevant / Total Retrieved
    faithfulness: float  # Claims Grounded in Context / Total Claims
    answer_relevance: float  # Match to User Intent
    overall_score: float = Field(..., ge=0.0, le=1.0)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))