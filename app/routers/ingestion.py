"""Document ingestion router."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status, BackgroundTasks

from app.core.security import require_user
from app.models.schemas import (
    DocumentIngestRequest,
    DocumentRecord,
    DocumentType,
    RBACMetadata,
    UserIdentity,
)
from app.services.etl import process_document_pipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DocumentRecord,
    summary="Upload a financial document for parsing and indexing",
)
async def upload_document(
    user: Annotated[UserIdentity, Depends(require_user)],
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File(...)],
    doc_type: Annotated[DocumentType, Form(...)],
    allowed_roles: Annotated[str, Form(...)],  # comma-separated
    fund_family: Annotated[str | None, Form(None)] = None,
    report_period: Annotated[str | None, Form(None)] = None,
) -> DocumentRecord:
    """Accept a raw document and enqueue it for async ETL processing."""
    
    roles_list = [r.strip() for r in allowed_roles.split(",") if r.strip()]

    # Generate the Document ID early to bind to the RBAC metadata payload
    document_id = str(uuid.uuid4())

    meta = DocumentIngestRequest(
        source_filename=file.filename or "unnamed",
        doc_type=doc_type,
        allowed_roles=roles_list,
        fund_family=fund_family,
        report_period=report_period,
    )

    rbac = RBACMetadata(
        allowed_roles=meta.allowed_roles,
        document_id=document_id,
        source_filename=meta.source_filename,
        uploaded_by=user.user_id,
        doc_type=meta.doc_type,
        fund_family=meta.fund_family,
        report_period=meta.report_period,
    )

    logger.info(
        "Upload received: %s by %s (roles=%s)",
        meta.source_filename,
        user.user_id,
        meta.allowed_roles,
    )

    # Read bytes immediately before the FastAPI file context closes
    file_bytes = await file.read()

    # Trigger the Phase 1 async ETL pipeline
    background_tasks.add_task(
        process_document_pipeline,
        file_bytes=file_bytes,
        filename=meta.source_filename,
        rbac=rbac,
    )

    return DocumentRecord(
        document_id=document_id,
        source_filename=meta.source_filename,
        doc_type=meta.doc_type,
        rbac=rbac,
        processing_status="processing",
    )