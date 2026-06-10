from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    fund_family: str | None = None
    report_period: str | None = None 

    @field_validator("allowed_roles")
    @classmethod
    def _roles_lowercase(cls, v: list[str]) -> list[str]:
        return [r.lower().strip() for r in v]


class UserIdentity(BaseModel):    

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



class DocumentIngestRequest(BaseModel):    

    source_filename: str = Field(..., min_length=1)
    doc_type: DocumentType
    allowed_roles: list[str] = Field(..., min_length=1)
    fund_family: str | None = None
    report_period: str | None = None
    # Raw file bytes uploaded via multipart; this model carries metadata only
    extra_metadata: dict[str, Any] = Field(default_factory=dict)


class ChunkPayload(BaseModel):    

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

    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_filename: str
    doc_type: DocumentType
    rbac: RBACMetadata
    chunk_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processing_status: str = "pending"  # pending | processing | completed | failed


class QueryRequest(BaseModel):    

    question: str = Field(..., min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20)
    # Optional: restrict search to specific document(s)
    filter_document_ids: list[str] | None = None


class RetrievedChunk(BaseModel):    

    chunk_id: str
    text: str
    score: float
    chunk_type: ChunkType
    rbac: RBACMetadata
    page_number: int | None = None


class RAGResponse(BaseModel):    

    answer: str
    sources: list[RetrievedChunk]
    latency_ms: float
    cache_hit: bool = False
    guardrail_passed: bool = True
    evaluation_score: dict[str, float] | None = None


class EvaluationResult(BaseModel):    

    context_relevance: float  # Retrieved Relevant / Total Retrieved
    faithfulness: float  # Claims Grounded in Context / Total Claims
    answer_relevance: float  
    overall_score: float = Field(..., ge=0.0, le=1.0)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))