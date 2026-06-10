
from __future__ import annotations

import pytest

from app.services.cache import SemanticCache
from app.services.llm import decompose_query


class DummySearchResult:
    def __init__(self, score: float, answer: bytes):
        self.docs = [type("Doc", (), {"score": score, "answer": answer})]


class DummyFt:
    def __init__(self, result):
        self._result = result

    async def search(self, *_args, **_kwargs):
        return self._result


@pytest.mark.asyncio
async def test_semantic_cache_hits_when_score_above_threshold(monkeypatch):
    cache = SemanticCache()
    cache.similarity_threshold = 0.90

    # Simulate a Redis search result with a strong similarity score.
    dummy_result = DummySearchResult(score=0.95, answer=b"cached answer")
    monkeypatch.setattr(cache.client, "ft", lambda _: DummyFt(dummy_result))

    answer = await cache.get([0.1, 0.2, 0.3], roles=["analyst"])

    assert answer == "cached answer"


@pytest.mark.asyncio
async def test_decompose_query_falls_back_to_original_on_json_parsing_issues(monkeypatch):
    class FakeResponse:
        def __init__(self, content):
            self.choices = [type("Choice", (), {"message": type("Message", (), {"content": content})})]

    async def fake_call_router_llm(prompt: str, query: str):
        return FakeResponse(
            "This is a malformed model output that contains embedded JSON: {\"sub_queries\": [\"revenue forecast\", \"cost trends\"]}"
        )

    monkeypatch.setattr("app.services.llm._call_router_llm", fake_call_router_llm)

    sub_queries = await decompose_query("What are the latest revenue and cost trends?")

    assert sub_queries == ["revenue forecast", "cost trends"]
