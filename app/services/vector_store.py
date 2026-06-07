"""Qdrant vector store client with RBAC-aware hybrid search.

Implements dense vector search + payload filtering for metadata roles.
The collection schema pre-indexes ``allowed_roles`` and ``document_id``
to prevent retrieval latency from scaling with collection size.
"""

from __future__ import annotations

import logging
from typing import Any

from qdrant_client import AsyncQdrantClient, models

from app.core.config import settings
from app.core.exceptions import VectorStoreError
from app.models.schemas import ChunkPayload, RetrievedChunk, UserIdentity

logger = logging.getLogger(__name__)

COLLECTION_NAME: str = settings.QDRANT_COLLECTION

# Pre-defined payload indices for RBAC enforcement performance
_PAYLOAD_INDICES: list[models.PayloadIndexSchema] = [
    models.PayloadIndexSchema(
        field="rbac.allowed_roles",
        field_index_type="keyword",
    ),
    models.PayloadIndexSchema(
        field="rbac.document_id",
        field_index_type="keyword",
    ),
    models.PayloadIndexSchema(
        field="rbac.fund_family",
        field_index_type="keyword",
    ),
]


class VectorStore:
    """Async Qdrant client wrapper with automatic collection management."""

    def __init__(self) -> None:
        self.client = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY or None,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def ensure_collection(self, vector_size: int) -> None:
        """Create collection if missing; ensure payload indices exist."""
        try:
            exists = await self.client.collection_exists(COLLECTION_NAME)
        except Exception as exc:
            raise VectorStoreError(f"Cannot reach Qdrant: {exc}") from exc

        if not exists:
            logger.info("Creating collection %s (dim=%d)", COLLECTION_NAME, vector_size)
            await self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                ),
                optimizers_config=models.OptimizersConfigDiff(
                    indexing_threshold=1000,
                ),
            )
            # Create payload indices for fast RBAC filtering
            for idx in _PAYLOAD_INDICES:
                await self.client.create_payload_index(
                    collection_name=COLLECTION_NAME,
                    field_name=idx.field,
                    field_schema=idx.field_index_type,
                    wait=True,
                )

    async def close(self) -> None:
        await self.client.close()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def upsert_chunks(self, chunks: list[ChunkPayload]) -> None:
        """Insert or update chunks with their embeddings."""
        if not chunks:
            return

        points = [
            models.PointStruct(
                id=ch.chunk_id,
                vector=ch.embedding,  # type: ignore[arg-type]
                payload={
                    "text": ch.text,
                    "chunk_type": ch.chunk_type.value,
                    "token_count": ch.token_count,
                    "page_number": ch.page_number,
                    "image_description": ch.image_description,
                    "rbac": ch.rbac.model_dump(mode="json"),
                },
            )
            for ch in chunks
            if ch.embedding is not None
        ]

        if not points:
            raise VectorStoreError("No chunks with embeddings to upsert")

        try:
            await self.client.upsert(collection_name=COLLECTION_NAME, points=points)
        except Exception as exc:
            raise VectorStoreError(f"Upsert failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Read — RBAC-enforced hybrid search
    # ------------------------------------------------------------------

    async def hybrid_search(
        self,
        user: UserIdentity,
        query_vector: list[float],
        top_k: int = 5,
        filter_document_ids: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        """Execute dense vector search with strict RBAC metadata pre-filter.

        The filter encodes the mathematical condition:
            metadata.allowed_roles ∩ user.permission_groups ≠ ∅
        """
        # Build RBAC condition: user must share at least one role with chunk
        rbac_conditions: list[models.Condition] = [
            models.FieldCondition(
                key="rbac.allowed_roles",
                match=models.MatchAny(any=[r.lower() for r in user.permission_groups]),
            )
        ]

        # Admin bypass — they see everything, so skip role filtering
        if user.is_admin:
            rbac_conditions = []

        # Optional: restrict to specific documents
        if filter_document_ids:
            rbac_conditions.append(
                models.FieldCondition(
                    key="rbac.document_id",
                    match=models.MatchAny(any=filter_document_ids),
                )
            )

        query_filter = (
            models.Filter(must=rbac_conditions) if rbac_conditions else None
        )

        try:
            results = await self.client.search(
                collection_name=COLLECTION_NAME,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=top_k,
                with_payload=True,
            )
        except Exception as exc:
            raise VectorStoreError(f"Search failed: {exc}") from exc

        return [_to_retrieved_chunk(r) for r in results]

    async def delete_by_document(self, document_id: str) -> None:
        """Remove all chunks belonging to a given document."""
        try:
            await self.client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="rbac.document_id",
                            match=models.MatchValue(value=document_id),
                        )
                    ]
                ),
            )
        except Exception as exc:
            raise VectorStoreError(f"Delete failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_retrieved_chunk(point: models.ScoredPoint) -> RetrievedChunk:
    """Map a Qdrant ScoredPoint back to our domain model."""
    from app.models.schemas import ChunkType, RBACMetadata

    payload: dict[str, Any] = point.payload or {}  # type: ignore[assignment]
    rbac_raw = payload.get("rbac", {})
    if isinstance(rbac_raw, str):
        import json
        rbac_raw = json.loads(rbac_raw)

    return RetrievedChunk(
        chunk_id=str(point.id),
        text=payload.get("text", ""),
        score=point.score,
        chunk_type=ChunkType(payload.get("chunk_type", "text")),
        rbac=RBACMetadata(**rbac_raw),
        page_number=payload.get("page_number"),
    )


# Singleton instance (initialised in lifespan)
vector_store = VectorStore()
