import asyncio
import logging
import torch
from concurrent.futures import ThreadPoolExecutor  # 1. Import ThreadPoolExecutor
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from app.core.config import settings
from app.models.schemas import RetrievedChunk

logger = logging.getLogger(__name__)

_tokenizer = None
_model = None

# 2. Instantiate a bounded executor
_executor = ThreadPoolExecutor(max_workers=1)

def _load_reranker():
    global _tokenizer, _model
    if _model is None:
        logger.info("Loading cross-encoder: %s", settings.RERANKER_MODEL)
        _tokenizer = AutoTokenizer.from_pretrained(settings.RERANKER_MODEL)
        _model = AutoModelForSequenceClassification.from_pretrained(settings.RERANKER_MODEL)
        _model.eval()
    return _tokenizer, _model

async def rerank_chunks(query: str, chunks: list[RetrievedChunk], top_k: int = 5) -> list[RetrievedChunk]:
    """Re-score chunks against the original query using a cross-encoder."""
    if not chunks:
        return []

    def _compute():
        tokenizer, model = _load_reranker()
        pairs = [[query, chunk.text] for chunk in chunks]
        
        with torch.no_grad():
            inputs = tokenizer(pairs, padding=True, truncation=True, return_tensors='pt', max_length=512)
            # Logits represent absolute relevance score
            scores = model(**inputs, return_dict=True).logits.view(-1,).float()
            
        for score, chunk in zip(scores, chunks):
            chunk.score = float(score.item())
            
        # Sort descending by the new cross-encoder score
        return sorted(chunks, key=lambda x: x.score, reverse=True)[:top_k]

    loop = asyncio.get_running_loop()
    # 3. Pass the custom _executor instead of None
    return await loop.run_in_executor(_executor, _compute)