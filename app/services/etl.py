"""Async ETL Pipeline for Document Ingestion."""

import asyncio
import logging
import os
import tempfile
import uuid
from typing import List

from llama_parse import LlamaParse
from sqlalchemy import update
from transformers import AutoTokenizer
from app.db.database import AsyncSessionLocal
from app.db.models import DocumentDBRecord
from app.core.config import settings
from app.models.schemas import ChunkPayload, ChunkType, RBACMetadata
from app.services.embeddings import encode, encode_sparse
from app.services.vector_store import vector_store
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.services.llm import generate_image_description

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

    ext = os.path.splitext(filename)[1]
    
    # 1. Safely acquire a low-level OS file descriptor
    fd, tmp_path = tempfile.mkstemp(suffix=ext)
    
    try:
        # Write bytes and force the OS to flush buffers to disk
        with os.fdopen(fd, 'wb') as f:
            f.write(file_bytes)
            f.flush()
            os.fsync(f.fileno()) 

        # 2. Layout-aware Parsing
        parser = LlamaParse(
            api_key=settings.LLAMA_CLOUD_API_KEY,
            result_type="markdown",
            premium_mode=True,
            verbose=False,
        )
        
        parsed_docs = await parser.aload_data(tmp_path)
        
        if not parsed_docs:
            logger.warning("No content could be extracted from %s", filename)
            await update_doc_status(rbac.document_id, "failed")
            return

        # 3. Chunking & Vision Processing
        chunks: List[ChunkPayload] = []
        
        for doc in parsed_docs:
            images = getattr(doc, 'images', []) 
            
            # 3A. Process Text
            raw_chunks = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
            
            for text in raw_chunks.split_text(doc.text):
                text = text.strip()
                if not text:
                    continue
                    
                is_table = "|" in text and "-|-" in text
                
                chunks.append(
                    ChunkPayload(
                        chunk_id=str(uuid.uuid4()),
                        text=text,
                        chunk_type=ChunkType.TABLE if is_table else ChunkType.TEXT,
                        rbac=rbac,
                        token_count=AutoTokenizer.from_pretrained("bert-base-uncased", use_fast=True).encode(text, return_tensors="pt").shape[1],
                    )
                )
            
            # 3B. Process Images
            for img_dict in images:
                base64_data = img_dict.get('base64') 
                if base64_data:
                    logger.info("Image detected. Routing to Vision LLM for description.")
                    img_desc = await generate_image_description(base64_data)
                    
                    chunks.append(
                        ChunkPayload(
                            chunk_id=str(uuid.uuid4()),
                            text=f"Image Description: {img_desc}",
                            chunk_type=ChunkType.IMAGE_DESCRIPTION,
                            image_description=img_desc,
                            rbac=rbac,
                            token_count=AutoTokenizer.from_pretrained("bert-base-uncased", use_fast=True).encode(img_desc, return_tensors="pt").shape[1],
                        )
                    )

        if not chunks:
            logger.warning("No valid chunks generated for %s", filename)
            await update_doc_status(rbac.document_id, "failed")
            return

        # 4. Embed Chunks
        logger.info("Encoding %d chunks for document %s", len(chunks), rbac.document_id)
        texts_to_embed = [c.text for c in chunks]
              
        embeddings, sparse_embeddings = await asyncio.gather(
            encode(texts_to_embed),
            encode_sparse(texts_to_embed)
        )
        
        for chunk, emb, sparse_emb in zip(chunks, embeddings, sparse_embeddings):
            chunk.embedding = emb
            chunk.sparse_embedding = sparse_emb

        # 5. Upsert to Vector Store (Qdrant)
        logger.info("Upserting %d chunks to vector store", len(chunks))
        await vector_store.upsert_chunks(chunks)
        
        # Mark as completed
        await update_doc_status(rbac.document_id, "completed")
        logger.info("ETL pipeline successfully completed for document %s", rbac.document_id)

    except Exception as exc:
        logger.error("ETL pipeline failed for document %s: %s", rbac.document_id, str(exc))
        await update_doc_status(rbac.document_id, "failed")
        raise    
    finally:
        # 6. Guaranteed Cleanup
        # Strict exception handling here prevents a cleanup failure from crashing the worker
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                logger.debug("Successfully cleaned up temporary file: %s", tmp_path)
        except OSError as cleanup_error:
            logger.error("Failed to clean up temporary file %s: %s", tmp_path, cleanup_error)


def _basic_markdown_chunker(text: str, max_chars: int = 1500) -> List[str]:
    """Naively chunks markdown by double-newlines."""
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""

    for p in paragraphs:
        if len(current_chunk) + len(p) > max_chars and current_chunk:
            chunks.append(current_chunk)
            current_chunk = p + "\n\n"
        else:
            current_chunk += p + "\n\n"
            
    if current_chunk:
        chunks.append(current_chunk)
        
    return chunks

async def update_doc_status(document_id: str, doc_status: str):
    """Updates database record status."""
    async with AsyncSessionLocal() as session:
        stmt = update(DocumentDBRecord).where(DocumentDBRecord.document_id == document_id).values(status=doc_status)
        await session.execute(stmt)
        await session.commit()