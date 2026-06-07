import logging
import uuid

import numpy as np
import redis.asyncio as redis
from redis.commands.search.query import Query

from app.core.config import settings

logger = logging.getLogger(__name__)

class SemanticCache:
    def __init__(self) -> None:
        self.client = redis.from_url(settings.REDIS_URL, decode_responses=False)
        self.index_name = "idx:semantic_cache"
        self.similarity_threshold = 0.95  # Cosine similarity threshold for a "hit"

    async def get(self, query_vector: list[float]) -> str | None:
        """Retrieve the semantically closest cached answer using Redis Vector Search."""
        try:
            # Convert python float list to raw bytes for Redis ingestion
            vector_bytes = np.array(query_vector, dtype=np.float32).tobytes()
            
            # KNN search: Find the top 1 nearest neighbor
            q = Query("*=>[KNN 1 @embedding $vec AS score]") \
                .return_fields("answer", "score") \
                .sort_by("score") \
                .dialect(2)
            
            res = await self.client.ft(self.index_name).search(
                q, query_params={"vec": vector_bytes}
            )
            
            if res.docs:
                # Redis returns distance (0 = exact match). Cosine Similarity = 1 - distance.
                score = float(res.docs[0].score)
                if (1.0 - score) >= self.similarity_threshold:
                    logger.info("Semantic cache hit! Score: %f", 1.0 - score)
                    # Decode answer since we initialized redis with decode_responses=False
                    return res.docs[0].answer.decode('utf-8')
                    
            return None
            
        except Exception as exc:
            # Degrade gracefully if the cache is unreachable or index is missing
            logger.warning("Semantic cache lookup skipped/failed: %s", exc)
            return None

    async def set(self, query_vector: list[float], answer: str, ttl_seconds: int = 3600) -> None:
        """Cache the query vector and the synthesized answer."""
        try:
            cache_id = f"cache:{uuid.uuid4()}"
            vector_bytes = np.array(query_vector, dtype=np.float32).tobytes()
            
            # Store in Redis as a Hash
            await self.client.hset(cache_id, mapping={
                "embedding": vector_bytes,
                "answer": answer.encode('utf-8')
            })
            # Set TTL to prevent stale data accumulation
            await self.client.expire(cache_id, ttl_seconds)
            
        except Exception as exc:
            logger.error("Failed to set semantic cache: %s", exc)

# Singleton export
semantic_cache = SemanticCache()