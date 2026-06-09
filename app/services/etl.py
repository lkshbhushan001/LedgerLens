"""Async ETL Pipeline for Document Ingestion."""

import asyncio
import logging
import os
import tempfile
import uuid
from typing import List

import pdfplumber 
from llama_parse import LlamaParse
from sqlalchemy import update
from transformers import AutoTokenizer
from app.db.database import AsyncSessionLocal
from app.db.models import DocumentDBRecord
from app.core.config import settings
from app.models.schemas import ChunkPayload, ChunkType, RBACMetadata
from app.services.embeddings import encode, encode_sparse
from app.services.vector_store import vector_store

_gpt2_tokenizer: AutoTokenizer | None = None

def _get_gpt2_tokenizer() -> AutoTokenizer:
    global _gpt2_tokenizer
    if _gpt2_tokenizer is None:
        _gpt2_tokenizer = AutoTokenizer.from_pretrained("gpt2")
    return _gpt2_tokenizer
from app.services.llm import generate_image_description

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fallback Logic
# ---------------------------------------------------------------------------

class MockDocument:
    """A mock object that mimics LlamaParse's document structure (.text, .images)"""
    def __init__(self, text: str):
        self.text = text
        self.images = []

def _local_pdf_fallback(file_path: str) -> list[MockDocument]:
    """Synchronous fallback parser using pdfplumber."""
    logger.warning("Executing local parsing via pdfplumber for: %s", file_path)
    
    fallback_docs = []
    try:
        with pdfplumber.open(file_path) as pdf:
            full_text = []
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text()
                if text:
                    full_text.append(f"--- Page {page_num} ---\n{text}")
            
            combined_text = "\n\n".join(full_text)

            if combined_text.strip():
                fallback_docs.append(MockDocument(combined_text))
                logger.info("Successfully extracted text from %d pages using local fallback.", len(pdf.pages))
            else:
                logger.error("Local fallback extracted zero text from the document.")
                
    except Exception as fallback_exc:
        logger.error("Critical Failure: Local fallback parser also failed: %s", fallback_exc)
        raise fallback_exc

    return fallback_docs

# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

async def process_document_pipeline(
    file_bytes: bytes,
    filename: str,
    rbac: RBACMetadata,
) -> None:
    """
    Executes the full ETL pipeline asynchronously:
    1. Layout-Aware Parsing (LlamaParse) with Local Fallback
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
            premium_mode=True,  # Ensure premium_mode is True to extract images
            verbose=False,
        )
        
        # --- ROBUST FALLBACK INTEGRATION ---
        try:
            logger.info("Attempting LlamaParse on %s", filename)
            parsed_docs = await parser.aload_data(tmp_path)
        except Exception as parse_exc:
            logger.warning("LlamaParse API failed (%s). Triggering pdfplumber fallback.", parse_exc)
            loop = asyncio.get_running_loop()
            # Run the synchronous fallback in a thread pool to avoid blocking the async event loop
            parsed_docs = await loop.run_in_executor(None, _local_pdf_fallback, tmp_path)
        # -----------------------------------

        if not parsed_docs:
            logger.warning("No content could be extracted from %s", filename)
            await update_doc_status(rbac.document_id, "failed")
            return

        # 3. Chunking & Vision Processing
        chunks: List[ChunkPayload] = []
        
        for doc in parsed_docs:
            images = getattr(doc, 'images', []) 
            
            # 3A. Process Text (Now fully compatible with MockDocument from fallback)
            raw_chunks = _basic_markdown_chunker(doc.text, max_chars=1500)
            for text in raw_chunks:
                text = text.strip()
                if not text:
                    continue
                    
                is_table = "|" in text and "-|-" in text
                
tokenizer = _get_gpt2_tokenizer()
                    chunks.append(
                        ChunkPayload(
                            chunk_id=str(uuid.uuid4()),
                            text=text,
                            chunk_type=ChunkType.TABLE if is_table else ChunkType.TEXT,
                            rbac=rbac,
                            token_count=len(tokenizer.encode(text, add_special_tokens=False)),
                    )
                )
            
            # 3B. Process Images (Will safely be skipped if using MockDocument)
            for img_dict in images:
                base64_data = img_dict.get('base64') 
                if base64_data:
                    logger.info("Image detected. Routing to Vision LLM for description.")
                    img_desc = await generate_image_description(base64_data)
                    
                    tokenizer = _get_gpt2_tokenizer()
                    chunks.append(
                        ChunkPayload(
                            chunk_id=str(uuid.uuid4()),
                            text=f"Image Description: {img_desc}",
                            chunk_type=ChunkType.IMAGE_DESCRIPTION,
                            image_description=img_desc,
                            rbac=rbac,
                            token_count=len(tokenizer.encode(img_desc, add_special_tokens=False)),
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
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                logger.debug("Successfully cleaned up temporary file: %s", tmp_path)
        except OSError as cleanup_error:
            logger.error("Failed to clean up temporary file %s: %s", tmp_path, cleanup_error)


def _basic_markdown_chunker(text: str, max_chars: int = 1500) -> List[str]:
    """Naively chunks markdown by double-newlines. (Consider adding overlap in future!)"""
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