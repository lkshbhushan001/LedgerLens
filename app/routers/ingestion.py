"""Document ingestion router.

Accepts file uploads + metadata, triggers the async ETL pipeline
(layout-aware parse → chunk → embed → vector insert).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.core.security import require_user
from app.models.schemas import (
    DocumentIngestRequest,
    DocumentRecord,
    DocumentType,
    RBACMetadata,
    UserIdentity,
)

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
    file: Annotated[UploadFile, File(...)],
    doc_type: Annotated[DocumentType, Form(...)],
    allowed_roles: Annotated[str, Form(...)],  # comma-separated
    fund_family: Annotated[str | None, Form(None)],
    report_period: Annotated[str | None, Form(None)],
) -> DocumentRecord:
    """Accept a raw document and enqueue it for async ETL processing.

    **allowed_roles**: comma-separated list, e.g. ``fund-a,analyst,compliance``.
    These roles are baked into every chunk's metadata for RBAC enforcement.
    """
    roles_list = [r.strip() for r in allowed_roles.split(",") if r.strip()]

    meta = DocumentIngestRequest(
        source_filename=file.filename or "unnamed",
        doc_type=doc_type,
        allowed_roles=roles_list,
        fund_family=fund_family,
        report_period=report_period,
    )

    rbac = RBACMetadata(
        allowed_roles=meta.allowed_roles,
        document_id="pending",  # assigned after file persistence
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

    # TODO Phase 2: persist file to object store, trigger async Celery / arq ETL job

    return DocumentRecord(
        source_filename=meta.source_filename,
        doc_type=meta.doc_type,
        rbac=rbac,
        processing_status="pending",
    )
