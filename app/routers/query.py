"""Query / RAG router.

Implements the runtime pipeline:
  Semantic Cache → Input Guardrail → Decomposition Router →
  Hybrid Search (RBAC-filtered) → Rerank → Compress → LLM → Output Guardrail

Only the retrieval layer (hybrid search with RBAC) is wired in this scaffold;
the remaining stages (cache, guardrails, router, reranker, compressor)
are stubbed with TODO markers for Phase 3/4.
"""

from __future__ import annotations

import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.security import require_user
from app.models.schemas import (
    QueryRequest,
    RAGResponse,
    RetrievedChunk,
    UserIdentity,
)
from app.services.embeddings import encode_query
from app.services.vector_store import vector_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/query", tags=["query"])


@router.post(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=RAGResponse,
    summary="Execute an RBAC-enforced RAG query",
)
async def query_rag(
    user: Annotated[UserIdentity, Depends(require_user)],
    request: QueryRequest,
) -> RAGResponse:
    """Run the full RAG pipeline for the authenticated user.

    RBAC enforcement happens at the vector store layer via metadata pre-filter.
    """
    t0 = time.perf_counter()

    # TODO Phase 4: Semantic cache lookup (GPTCache / Redis vector cache)
    cache_hit = False

    # TODO Phase 4: Input guardrail — prompt injection / adversarial detection

    # TODO Phase 3: Query decomposition router — split multi-intent queries

    # ---- Dense retrieval (RBAC-enforced) ----
    query_vector = await encode_query(request.question)
    chunks: list[RetrievedChunk] = await vector_store.hybrid_search(
        user=user,
        query_vector=query_vector,
        top_k=request.top_k,
        filter_document_ids=request.filter_document_ids,
    )

    # TODO Phase 3: Sparse keyword search (BM25) + score fusion
    # Score = α * score_dense + (1 − α) * score_sparse

    # TODO Phase 4: Cross-encoder reranking (BGE-Reranker)

    # TODO Phase 4: Contextual compression (LLMLingua)

    # ---- Synthesis (placeholder) ----
    if chunks:
        context = "\n\n".join(f"[{i+1}] {c.text}" for i, c in enumerate(chunks))
        answer = f"[Synthesized answer based on {len(chunks)} retrieved chunks]\n\n{context[:500]}..."
    else:
        answer = "No relevant documents found for your permission level."

    # TODO Phase 4: Output guardrail — PII / restricted metric filtering
    # TODO Phase 5: Evaluation harness (Ragas) — faithfulness, context relevance

    latency_ms = (time.perf_counter() - t0) * 1000

    logger.info(
        "Query processed",
        extra={
            "user_id": user.user_id,
            "question": request.question[:80],
            "chunks_retrieved": len(chunks),
            "latency_ms": round(latency_ms, 2),
            "cache_hit": cache_hit,
        },
    )

    return RAGResponse(
        answer=answer,
        sources=chunks,
        latency_ms=round(latency_ms, 2),
        cache_hit=cache_hit,
        guardrail_passed=True,
    )
