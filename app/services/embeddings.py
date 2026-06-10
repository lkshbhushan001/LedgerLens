
from __future__ import annotations

import asyncio
import logging
from functools import partial
import collections
from transformers import AutoTokenizer

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import settings

logger = logging.getLogger(__name__)
_sparse_tokenizer = None
_model: SentenceTransformer | None = None


def _load_model() -> SentenceTransformer:
    # Lazy-load the embedding model to avoid startup overhead if not needed immediately.
    global _model
    if _model is None:
        logger.info("Loading embedding model: %s", settings.EMBEDDING_MODEL)
        _model = SentenceTransformer(
            settings.EMBEDDING_MODEL,
            device=settings.EMBEDDING_DEVICE,
            trust_remote_code=True,
        )
    return _model


async def encode(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    
    if not texts:
        return []

    model = _load_model()
    loop = asyncio.get_running_loop()
    fn = partial(
        model.encode,
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,  
    )
    embeddings: np.ndarray = await loop.run_in_executor(None, fn)
    return embeddings.tolist()


async def encode_query(text: str) -> list[float]:    
    results = await encode([text], batch_size=1)
    return results[0]


def get_vector_size() -> int:    
    model = _load_model()
    return model.get_embedding_dimension()

def _load_sparse_tokenizer():    
    global _sparse_tokenizer
    if _sparse_tokenizer is None:
        logger.info("Loading sparse tokenizer: bert-base-uncased")        
        _sparse_tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased", use_fast=True)
    return _sparse_tokenizer

async def encode_sparse(texts: list[str]) -> list[dict[str, list]]:    
    if not texts:
        return []
        
    tokenizer = _load_sparse_tokenizer()
    loop = asyncio.get_running_loop()
    
    def _process():
        results = []
        for text in texts:
            # Tokenize without special tokens to get raw word components
            tokens = tokenizer.encode(text, add_special_tokens=False)
            counts = collections.Counter(tokens)
            results.append({
                "indices": list(counts.keys()),
                "values": [float(v) for v in counts.values()]
            })
        return results

    return await loop.run_in_executor(None, _process)

async def encode_query_sparse(text: str) -> dict[str, list]:    
    results = await encode_sparse([text])
    return results[0]
