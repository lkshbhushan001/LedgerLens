"""Mock integration test covering ingestion and query flow."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import RBACMetadata, RetrievedChunk


async def _fake_process_document_pipeline(file_bytes: bytes, filename: str, rbac: object) -> None:
    from app.services.etl import update_doc_status

    await update_doc_status(rbac.document_id, "completed")


def test_ingest_and_query_flow(monkeypatch):
    client = TestClient(app)

    # Patch ingestion background pipeline to avoid external dependencies
    monkeypatch.setattr("app.routers.ingestion.process_document_pipeline", _fake_process_document_pipeline)

    # Patch query pipeline components to return deterministic search results
    monkeypatch.setattr("app.routers.query.decompose_query", lambda query: [query])
    monkeypatch.setattr("app.routers.query.semantic_cache.get", lambda query_vector, roles: None)
    monkeypatch.setattr("app.routers.query.semantic_cache.set", lambda query_vector, answer, roles: None)
    monkeypatch.setattr("app.routers.query.encode_query", lambda q: [0.0, 0.0, 0.0])
    monkeypatch.setattr("app.routers.query.encode_query_sparse", lambda q: {"indices": [1], "values": [1.0]})

    dummy_chunk = RetrievedChunk(
        chunk_id="chunk-1",
        text="Financial report summary",
        score=0.9,
        chunk_type="text",
        rbac=RBACMetadata(
            allowed_roles=["analyst"],
            document_id="doc-1",
            source_filename="report.pdf",
            uploaded_by="test-user",
            doc_type="pdf",
        ),
        page_number=1,
    )

    monkeypatch.setattr("app.routers.query.vector_store.hybrid_search", lambda *args, **kwargs: [dummy_chunk])
    monkeypatch.setattr("app.routers.query.rerank_chunks", lambda query, chunks, top_k=5: [dummy_chunk])
    monkeypatch.setattr("app.routers.query.compress_context", lambda question, texts: "compressed context")
    monkeypatch.setattr("app.routers.query.generate_answer", lambda question, context: "This is a test answer.")

    # Obtain a test JWT
    token_resp = client.post(
        "/auth/token",
        json={
            "user_id": "test-user",
            "email": "test@example.com",
            "permission_groups": ["analyst"],
            "is_admin": False,
        },
    )
    assert token_resp.status_code == 200
    token = token_resp.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}

    # Upload a document and ensure ingestion endpoint accepts it
    ingest_resp = client.post(
        "/ingest/upload",
        headers=headers,
        data={
            "doc_type": "pdf",
            "allowed_roles": "analyst",
            "fund_family": "FundA",
            "report_period": "2026-Q2",
        },
        files={"file": ("report.pdf", b"fake pdf bytes")},
    )

    assert ingest_resp.status_code == 202
    payload = ingest_resp.json()
    assert payload["processing_status"] == "processing"
    assert payload["doc_type"] == "pdf"
    document_id = payload["document_id"]

    # Check ingestion status after the background task has run
    status_resp = client.get(f"/ingest/{document_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "completed"

    # Query the RAG endpoint and verify the mocked response
    query_resp = client.post(
        "/query/",
        headers=headers,
        json={"question": "What is the revenue outlook?", "top_k": 1},
    )

    assert query_resp.status_code == 200
    result = query_resp.json()
    assert result["answer"] == "This is a test answer."
    assert result["cache_hit"] is False
    assert len(result["sources"]) == 1
