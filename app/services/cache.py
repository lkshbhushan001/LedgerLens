import hashlib
import logging
import uuid

import numpy as np
import redis.asyncio as redis
from redis.commands.search.field import VectorField, TextField, TagField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from redis.exceptions import ResponseError
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.config import settings

logger = logging.getLogger(__name__)

class SemanticCache:
    def __init__(self) -> None:
        self.client = redis.from_url(settings.REDIS_URL, decode_responses=False)
        self.index_name = "idx:semantic_cache"
        self.similarity_threshold = 0.95 

    def _get_role_hash(self, roles: list[str]) -> str:
        """Create a deterministic hash of the sorted roles to use as a cache partition."""
        sorted_roles = sorted([r.lower().strip() for r in roles])
        return hashlib.sha256(",".join(sorted_roles).encode()).hexdigest()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=5), reraise=True)
    async def initialize_index(self, vector_dim: int) -> None:
        """Create the semantic cache vector index if it does not exist."""
        try:
            await self.client.ft(self.index_name).info()
            logger.info("Semantic cache index '%s' already exists.", self.index_name)
        except ResponseError:
            logger.info("Creating semantic cache index '%s' with dim %d...", self.index_name, vector_dim)
            schema = (
                TagField("role_hash"),  # <-- Added to partition cache by RBAC roles
                VectorField(
                    "embedding",
                    "HNSW",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": vector_dim,
                        "DISTANCE_METRIC": "COSINE",
                    }
                ),
                TextField("answer"),
            )
            definition = IndexDefinition(prefix=["cache:"], index_type=IndexType.HASH)
            await self.client.ft(self.index_name).create_index(fields=schema, definition=definition)
            logger.info("Semantic cache index created successfully.")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=5), reraise=True)
    async def get(self, query_vector: list[float], roles: list[str]) -> str | None:
        """Retrieve the semantically closest cached answer isolated by RBAC role hash."""
        try:
            role_hash = self._get_role_hash(roles)
            vector_bytes = np.array(query_vector, dtype=np.float32).tobytes()
            
            # KNN search: Filter by role_hash FIRST, then find nearest neighbor
            q = Query(f"(@role_hash:{{{role_hash}}})=>[KNN 1 @embedding $vec AS score]") \
                .return_fields("answer", "score") \
                .sort_by("score") \
                .dialect(2)
            
            res = await self.client.ft(self.index_name).search(
                q, query_params={"vec": vector_bytes}
            )
            
            if res.docs:
                score = float(res.docs[0].score)
                if (1.0 - score) >= self.similarity_threshold:
                    logger.info("Semantic cache hit! Score: %f", 1.0 - score)
                    return res.docs[0].answer.decode('utf-8')
                    
            return None
            
        except Exception as exc:
            logger.warning("Semantic cache lookup skipped/failed: %s", exc)
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=5), reraise=True)
    async def set(self, query_vector: list[float], answer: str, roles: list[str], ttl_seconds: int = 3600) -> None:
        """Cache the query vector, the role hash, and the synthesized answer."""
        try:
            role_hash = self._get_role_hash(roles)
            cache_id = f"cache:{uuid.uuid4()}"
            vector_bytes = np.array(query_vector, dtype=np.float32).tobytes()
            
            await self.client.hset(cache_id, mapping={
                "role_hash": role_hash,  # <-- Store the hash with the cached record
                "embedding": vector_bytes,
                "answer": answer.encode('utf-8')
            })
            await self.client.expire(cache_id, ttl_seconds)
            
        except Exception as exc:
            logger.error("Failed to set semantic cache: %s", exc)

semantic_cache = SemanticCache()