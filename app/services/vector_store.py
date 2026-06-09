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

    async def close(self) -> None:
        await self.client.close()

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
                # Upgrade to Named Vectors to support hybrid indexing
                vectors_config={
                    "dense": models.VectorParams(
                        size=vector_size,
                        distance=models.Distance.COSINE,
                    )
                },
                sparse_vectors_config={
                    "bm25": models.SparseVectorParams(
                        modifier=models.Modifier.IDF  # Qdrant calculates IDF server-side
                    )
                },
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

    async def upsert_chunks(self, chunks: list[ChunkPayload]) -> None:
        if not chunks:
            return

        points = [
            models.PointStruct(
                id=ch.chunk_id,
                vector={
                    "dense": ch.embedding,
                    "bm25": models.SparseVector(
                        indices=ch.sparse_embedding["indices"],
                        values=ch.sparse_embedding["values"]
                    ) if ch.sparse_embedding else None
                },
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

    async def hybrid_search(
        self,
        user: UserIdentity,
        query_vector: list[float],
        query_sparse: dict[str, list],
        top_k: int = 5,
        filter_document_ids: list[str] | None = None,
        alpha: float = 0.5, # 0.5 = equal weight
    ) -> list[RetrievedChunk]:
        """Execute parallel Dense and Sparse searches, then fuse normalized scores."""
        rbac_conditions = [
            models.FieldCondition(
                key="rbac.allowed_roles",
                match=models.MatchAny(any=[r.lower() for r in user.permission_groups]),
            )
        ]

        if user.is_admin:
            rbac_conditions = []

        if filter_document_ids:
            rbac_conditions.append(
                models.FieldCondition(
                    key="rbac.document_id",
                    match=models.MatchAny(any=filter_document_ids),
                )
            )

        query_filter = models.Filter(must=rbac_conditions) if rbac_conditions else None

        # 1. Execute Dense Search
        dense_results = await self.client.search(
            collection_name=COLLECTION_NAME,
            query_vector=("dense", query_vector),
            query_filter=query_filter,
            limit=top_k * 2, # Fetch wider net for better fusion overlap
            with_payload=True,
        )

        # 2. Execute Sparse Search (BM25)
        sparse_results = await self.client.search(
            collection_name=COLLECTION_NAME,
            query_vector=("bm25", models.SparseVector(
                indices=query_sparse["indices"], 
                values=query_sparse["values"]
            )),
            query_filter=query_filter,
            limit=top_k * 2,
            with_payload=True,
        )

        # 3. Min-Max Normalization helper (Relative Score Fusion)
        def normalize(results: list[models.ScoredPoint]) -> dict[str, tuple[float, models.ScoredPoint]]:
            if not results: return {}
            scores = [r.score for r in results]
            min_score, max_score = min(scores), max(scores)
            
            normalized = {}
            for r in results:
                # Handle edge case where all retrieved scores are identical
                norm_val = (r.score - min_score) / (max_score - min_score) if max_score > min_score else 1.0
                normalized[str(r.id)] = (norm_val, r)
            return normalized

        dense_norm = normalize(dense_results)
        sparse_norm = normalize(sparse_results)

        # 4. Math Fusion: α * score_dense + (1 − α) * score_sparse
        fused_scores = {}
        all_ids = set(dense_norm.keys()).union(sparse_norm.keys())

        for pid in all_ids:
            d_score, d_point = dense_norm.get(pid, (0.0, None))
            s_score, s_point = sparse_norm.get(pid, (0.0, None))
            
            final_score = (alpha * d_score) + ((1.0 - alpha) * s_score)
            point_data = d_point if d_point else s_point
            
            fused_scores[pid] = (final_score, point_data)

        # Sort by fused score descending
        ranked_results = sorted(fused_scores.values(), key=lambda x: x[0], reverse=True)
        top_results = ranked_results[:top_k]

        return [_to_retrieved_chunk(pt, score) for score, pt in top_results]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Ensure the helper accepts the new fused score
def _to_retrieved_chunk(point: models.ScoredPoint, custom_score: float | None = None) -> RetrievedChunk:
    from app.models.schemas import ChunkType, RBACMetadata
    
    payload = point.payload or {}
    rbac_raw = payload.get("rbac", {})
    if isinstance(rbac_raw, str):
        import json
        rbac_raw = json.loads(rbac_raw)

    return RetrievedChunk(
        chunk_id=str(point.id),
        text=payload.get("text", ""),
        score=custom_score if custom_score is not None else point.score,
        chunk_type=ChunkType(payload.get("chunk_type", "text")),
        rbac=RBACMetadata(**rbac_raw),
        page_number=payload.get("page_number"),
    )


vector_store = VectorStore()

