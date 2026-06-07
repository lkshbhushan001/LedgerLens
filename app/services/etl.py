"""Async ETL Pipeline for Document Ingestion."""

import asyncio
import logging
import os
import tempfile
import uuid
from typing import List

from llama_parse import LlamaParse

from app.core.config import settings
from app.models.schemas import ChunkPayload, ChunkType, RBACMetadata
from app.services.embeddings import encode, encode_sparse
from app.services.vector_store import vector_store

logger = logging.getLogger(__name__)

async def process_document_pipeline(
    file_bytes: bytes,
    filename: str,
    rbac: RBACMetadata,
) -> None:
    """
    Executes the full ETL pipeline asynchronously:
    1. Layout-Aware Parsing (LlamaParse)
    2. Semantic Chunking
    3. Dense Vector Embedding
    4. Vector Store Upsert
    """
    logger.info("Starting ETL pipeline for document: %s", rbac.document_id)

    # 1. Save bytes to a temporary file for LlamaParse
    ext = os.path.splitext(filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        # 2. Layout-aware Parsing
        # Result type "markdown" ensures financial tables are preserved with standard md syntax
        parser = LlamaParse(
            api_key=settings.LLAMA_CLOUD_API_KEY,
            result_type="markdown",
            verbose=False,
        )
        
        parsed_docs = await parser.aload_data(tmp_path)
        
        if not parsed_docs:
            logger.warning("No content could be extracted from %s", filename)
            return

        # Combine parsed nodes into full text
        full_text = "\n\n".join([doc.text for doc in parsed_docs])

        # 3. Chunking
        # A simple paragraph-aware chunker that respects markdown structures
        raw_chunks = _basic_markdown_chunker(full_text, max_chars=1500)
        
        chunks: List[ChunkPayload] = []
        for text in raw_chunks:
            text = text.strip()
            if not text:
                continue
                
            # Classify chunk type to assist the decomposition router later
            is_table = "|" in text and "-|-" in text
            chunk_type = ChunkType.TABLE if is_table else ChunkType.TEXT
            
            chunks.append(
                ChunkPayload(
                    chunk_id=str(uuid.uuid4()),
                    text=text,
                    chunk_type=chunk_type,
                    rbac=rbac,
                    # Fast approximate token count (roughly 4 chars per token)
                    token_count=len(text) // 4,
                )
            )

        if not chunks:
            logger.warning("No valid chunks generated for %s", filename)
            return

        # 4. Embed Chunks
        logger.info("Encoding %d chunks for document %s", len(chunks), rbac.document_id)
        texts_to_embed = [c.text for c in chunks]
        
        # Await both dense and sparse encodings concurrently for better performance        
        embeddings, sparse_embeddings = await asyncio.gather(
            encode(texts_to_embed),
            encode_sparse(texts_to_embed)
        )
        
        # Attach both vectors to the chunk payload
        for chunk, emb, sparse_emb in zip(chunks, embeddings, sparse_embeddings):
            chunk.embedding = emb
            chunk.sparse_embedding = sparse_emb

        # 5. Upsert to Vector Store (Qdrant)
        logger.info("Upserting %d chunks to vector store", len(chunks))
        await vector_store.upsert_chunks(chunks)
        
        logger.info("ETL pipeline successfully completed for document %s", rbac.document_id)

    except Exception as exc:
        logger.error("ETL pipeline failed for document %s: %s", rbac.document_id, exc, exc_info=True)
        # TODO Phase 2: Update document status to "failed" in a relational database
        raise
    finally:
        # Ensure temporary file is always cleaned up
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def _basic_markdown_chunker(text: str, max_chars: int = 1500) -> List[str]:
    """
    Naively chunks markdown by double-newlines (paragraphs/tables)
    to avoid breaking internal table rows.
    """
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""

    for p in paragraphs:
        # If adding the next paragraph exceeds limit, commit current chunk
        if len(current_chunk) + len(p) > max_chars and current_chunk:
            chunks.append(current_chunk)
            current_chunk = p + "\n\n"
        else:
            current_chunk += p + "\n\n"
            
    if current_chunk:
        chunks.append(current_chunk)
        
    return chunks