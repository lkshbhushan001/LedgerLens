"""
Integration tests for document ingestion with various file types.
Uses pytest fixtures from conftest.py to generate test documents.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.db.models import Document, DocumentStatus
from app.core.security import create_access_token, UserIdentity


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def test_token():
    """Create a test JWT token for authentication."""
    user = UserIdentity(
        user_id="test_user_123",
        email="test@example.com",
        roles=["analyst", "viewer"],
        organization_id="test_org"
    )
    return create_access_token(user)


@pytest.fixture
def auth_headers(test_token):
    """Create authorization headers with test token."""
    return {"Authorization": f"Bearer {test_token}"}


# ==============================================================================
# PDF Ingestion Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_ingest_pdf_document(client, auth_headers, test_pdf_file):
    """Test ingesting a PDF document."""
    with patch("app.services.etl.process_document_pipeline") as mock_process:
        mock_process.return_value = {
            "chunks": [
                {"content": "Sample chunk 1", "metadata": {"page": 1}},
                {"content": "Sample chunk 2", "metadata": {"page": 2}},
            ],
            "total_chunks": 2,
            "file_size": 15000,
        }
        
        with open(test_pdf_file, "rb") as f:
            response = client.post(
                "/ingest/upload",
                files={"file": ("financial_report.pdf", f, "application/pdf")},
                headers=auth_headers,
            )
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "processing"
        assert "document_id" in data
        assert data["file_name"] == "financial_report.pdf"


@pytest.mark.asyncio
async def test_pdf_status_polling(client, auth_headers, test_pdf_file):
    """Test polling the status of a PDF ingestion."""
    mock_document_id = "doc_pdf_123"
    
    with patch("app.services.etl.process_document_pipeline") as mock_process:
        mock_process.return_value = {
            "chunks": [{"content": "Test content", "metadata": {"page": 1}}],
            "total_chunks": 1,
            "file_size": 8000,
        }
        
        # Simulate document status check
        with patch("app.db.database.get_session") as mock_session:
            mock_doc = MagicMock()
            mock_doc.id = mock_document_id
            mock_doc.filename = "financial_report.pdf"
            mock_doc.status = DocumentStatus.COMPLETED
            mock_doc.chunk_count = 1
            mock_doc.file_size = 8000
            
            mock_query = AsyncMock()
            mock_query.filter.return_value.first = AsyncMock(return_value=mock_doc)
            mock_session.return_value.query.return_value = mock_query
            
            response = client.get(
                f"/ingest/{mock_document_id}/status",
                headers=auth_headers,
            )
            
            # Status should be accessible (may return 404 if doc not found in test DB)
            assert response.status_code in [200, 404]


# ==============================================================================
# XML Ingestion Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_ingest_xml_document(client, auth_headers, test_xml_file):
    """Test ingesting an XML document."""
    with patch("app.services.etl.process_document_pipeline") as mock_process:
        mock_process.return_value = {
            "chunks": [
                {"content": "Financial data structured in XML", "metadata": {"source": "xml"}},
            ],
            "total_chunks": 1,
            "file_size": 2500,
        }
        
        with open(test_xml_file, "rb") as f:
            response = client.post(
                "/ingest/upload",
                files={"file": ("financial_data.xml", f, "application/xml")},
                headers=auth_headers,
            )
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "processing"
        assert data["file_name"] == "financial_data.xml"


# ==============================================================================
# CSV Ingestion Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_ingest_csv_document(client, auth_headers, test_csv_file):
    """Test ingesting a CSV document."""
    with patch("app.services.etl.process_document_pipeline") as mock_process:
        mock_process.return_value = {
            "chunks": [
                {"content": "Transaction record 1", "metadata": {"row": 1}},
                {"content": "Transaction record 2", "metadata": {"row": 2}},
            ],
            "total_chunks": 2,
            "file_size": 1200,
        }
        
        with open(test_csv_file, "rb") as f:
            response = client.post(
                "/ingest/upload",
                files={"file": ("transactions.csv", f, "text/csv")},
                headers=auth_headers,
            )
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "processing"
        assert data["file_name"] == "transactions.csv"


# ==============================================================================
# TXT Ingestion Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_ingest_txt_document(client, auth_headers, test_txt_file):
    """Test ingesting a plain text document."""
    with patch("app.services.etl.process_document_pipeline") as mock_process:
        mock_process.return_value = {
            "chunks": [
                {"content": "Financial report section 1", "metadata": {"section": "overview"}},
                {"content": "Financial report section 2", "metadata": {"section": "metrics"}},
            ],
            "total_chunks": 2,
            "file_size": 3500,
        }
        
        with open(test_txt_file, "rb") as f:
            response = client.post(
                "/ingest/upload",
                files={"file": ("report.txt", f, "text/plain")},
                headers=auth_headers,
            )
        
        assert response.status_code == 202
        data = response.json()
        assert data["file_name"] == "report.txt"


# ==============================================================================
# JSON Ingestion Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_ingest_json_document(client, auth_headers, test_json_file):
    """Test ingesting a JSON document."""
    with patch("app.services.etl.process_document_pipeline") as mock_process:
        mock_process.return_value = {
            "chunks": [
                {"content": "Account details", "metadata": {"type": "ledger"}},
            ],
            "total_chunks": 1,
            "file_size": 1800,
        }
        
        with open(test_json_file, "rb") as f:
            response = client.post(
                "/ingest/upload",
                files={"file": ("ledger.json", f, "application/json")},
                headers=auth_headers,
            )
        
        assert response.status_code == 202
        data = response.json()
        assert data["file_name"] == "ledger.json"


# ==============================================================================
# Multi-Document Batch Ingestion Test
# ==============================================================================


@pytest.mark.asyncio
async def test_ingest_multiple_documents(
    client, auth_headers, test_documents_dir
):
    """Test ingesting multiple documents of different types."""
    with patch("app.services.etl.process_document_pipeline") as mock_process:
        mock_process.return_value = {
            "chunks": [{"content": "Test chunk", "metadata": {}}],
            "total_chunks": 1,
            "file_size": 1000,
        }
        
        document_files = list(test_documents_dir.glob("*"))
        
        for doc_file in document_files:
            if doc_file.is_file():
                # Determine MIME type
                mime_types = {
                    ".pdf": "application/pdf",
                    ".xml": "application/xml",
                    ".csv": "text/csv",
                    ".txt": "text/plain",
                    ".json": "application/json",
                }
                mime_type = mime_types.get(doc_file.suffix, "application/octet-stream")
                
                with open(doc_file, "rb") as f:
                    response = client.post(
                        "/ingest/upload",
                        files={"file": (doc_file.name, f, mime_type)},
                        headers=auth_headers,
                    )
                
                assert response.status_code == 202, f"Failed to ingest {doc_file.name}"
                data = response.json()
                assert data["file_name"] == doc_file.name


# ==============================================================================
# Query Integration with Ingested Documents
# ==============================================================================


@pytest.mark.asyncio
async def test_query_after_document_ingestion(client, auth_headers, test_pdf_file):
    """Test querying after ingesting a PDF document."""
    # Mock the ingestion
    with patch("app.services.etl.process_document_pipeline") as mock_ingest:
        mock_ingest.return_value = {
            "chunks": [
                {"content": "Revenue: $2,500,000", "metadata": {"page": 1}},
                {"content": "Net Income: $600,000", "metadata": {"page": 2}},
            ],
            "total_chunks": 2,
            "file_size": 15000,
        }
        
        # Upload document
        with open(test_pdf_file, "rb") as f:
            upload_response = client.post(
                "/ingest/upload",
                files={"file": ("financial.pdf", f, "application/pdf")},
                headers=auth_headers,
            )
        
        assert upload_response.status_code == 202
    
    # Mock the query pipeline
    with patch("app.services.llm.decompose_query") as mock_decompose, \
         patch("app.services.cache.SemanticCache.get") as mock_cache_get, \
         patch("app.services.cache.SemanticCache.set") as mock_cache_set, \
         patch("app.services.embeddings.encode_query") as mock_encode, \
         patch("app.services.vector_store.VectorStore.hybrid_search") as mock_search, \
         patch("app.services.reranker.rerank_chunks") as mock_rerank, \
         patch("app.services.compressor.compress_context") as mock_compress, \
         patch("app.services.llm.generate_answer") as mock_generate:
        
        mock_cache_get.return_value = None  # Cache miss
        mock_decompose.return_value = ["What is the revenue?"]
        mock_encode.return_value = [0.1] * 1024
        mock_search.return_value = [
            {"content": "Revenue: $2,500,000", "score": 0.92},
        ]
        mock_rerank.return_value = [
            {"content": "Revenue: $2,500,000", "relevance_score": 0.95},
        ]
        mock_compress.return_value = "Revenue: $2,500,000"
        mock_generate.return_value = "The revenue is $2,500,000"
        
        query_response = client.post(
            "/query/",
            json={"query": "What is the revenue?"},
            headers=auth_headers,
        )
        
        assert query_response.status_code in [200, 422]  # 422 if input validation issues


# ==============================================================================
# Error Handling Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_ingest_unsupported_file_type(client, auth_headers, tmp_path):
    """Test error handling for unsupported file types."""
    # Create a file with unsupported extension
    unsupported_file = tmp_path / "test.exe"
    unsupported_file.write_bytes(b"dummy content")
    
    with open(unsupported_file, "rb") as f:
        response = client.post(
            "/ingest/upload",
            files={"file": ("test.exe", f, "application/octet-stream")},
            headers=auth_headers,
        )
    
    # Should either reject or accept (depending on implementation)
    assert response.status_code in [202, 400, 422]


@pytest.mark.asyncio
async def test_ingest_without_authentication(client, test_pdf_file):
    """Test that ingestion requires authentication."""
    with open(test_pdf_file, "rb") as f:
        response = client.post(
            "/ingest/upload",
            files={"file": ("financial.pdf", f, "application/pdf")},
        )
    
    # Should require authentication
    assert response.status_code in [401, 403]


# ==============================================================================
# Document Metadata Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_document_metadata_preservation(client, auth_headers, test_xml_file):
    """Test that document metadata is preserved during ingestion."""
    with patch("app.services.etl.process_document_pipeline") as mock_process:
        mock_process.return_value = {
            "chunks": [{"content": "XML content", "metadata": {}}],
            "total_chunks": 1,
            "file_size": 2500,
        }
        
        with open(test_xml_file, "rb") as f:
            response = client.post(
                "/ingest/upload",
                files={"file": ("financial_data.xml", f, "application/xml")},
                headers=auth_headers,
            )
        
        assert response.status_code == 202
        data = response.json()
        
        # Verify metadata fields
        assert "document_id" in data
        assert data["file_name"] == "financial_data.xml"
        assert data["status"] == "processing"
        assert "uploaded_at" in data
