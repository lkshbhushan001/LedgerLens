
import time
import asyncio
import logging
from typing import Annotated
from fastapi import APIRouter, Depends, status
from app.services.llm import decompose_query, generate_answer
from app.services.reranker import rerank_chunks
from app.services.compressor import compress_context
from app.core.security import require_user
from app.models.schemas import QueryRequest, RAGResponse, RetrievedChunk, UserIdentity
from app.services.embeddings import encode_query, encode_query_sparse
from app.services.vector_store import vector_store

from app.services.cache import semantic_cache
from app.services.guardrails import check_input_guardrails, apply_output_guardrails

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/query", tags=["query"])

@router.post("/")
async def query_rag(
    user: Annotated[UserIdentity, Depends(require_user)],
    request: QueryRequest,
) -> RAGResponse:
    t0 = time.perf_counter()
   
    check_input_guardrails(request.question)
    query_vector = await encode_query(request.question)    
    
    cached_answer = await semantic_cache.get(query_vector, roles=user.permission_groups)
    
    if cached_answer:
        return RAGResponse(
            answer=apply_output_guardrails(cached_answer),
            sources=[], latency_ms=round((time.perf_counter() - t0)*1000, 2), cache_hit=True
        )
    
    sub_queries = await decompose_query(request.question)
        
    pooled_chunks = {}
    
    async def _search_sub_query(sq: str):
        sq_dense = await encode_query(sq)
        sq_sparse = await encode_query_sparse(sq)        
        return await vector_store.hybrid_search(
            user=user, query_vector=sq_dense, query_sparse=sq_sparse, 
            top_k=request.top_k * 2, filter_document_ids=request.filter_document_ids
        )

    search_tasks = [_search_sub_query(sq) for sq in sub_queries]
    search_results_lists = await asyncio.gather(*search_tasks)
    
    for results in search_results_lists:
        for chunk in results:
            if chunk.chunk_id not in pooled_chunks:
                pooled_chunks[chunk.chunk_id] = chunk

    unique_chunks = list(pooled_chunks.values())
    
    reranked_chunks = await rerank_chunks(
        query=request.question,
        chunks=unique_chunks,
        top_k=request.top_k
    )
    
    if reranked_chunks:
        raw_texts = [c.text for c in reranked_chunks]        
        
        compressed_context = await compress_context(request.question, raw_texts)        
        
        answer = await generate_answer(request.question, compressed_context)
    else:
        answer = "No relevant documents found for your permission level."
   
    safe_answer = apply_output_guardrails(answer)
    if reranked_chunks:
        # Pass user roles to isolate the cache storage
        await semantic_cache.set(query_vector, safe_answer, roles=user.permission_groups)
    latency_ms = (time.perf_counter() - t0) * 1000

    return RAGResponse(
        answer=safe_answer,
        sources=reranked_chunks,
        latency_ms=round(latency_ms, 2),
        cache_hit=False,
        guardrail_passed=True,
    )