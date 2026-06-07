import asyncio
import logging
from llmlingua import PromptCompressor

logger = logging.getLogger(__name__)

_compressor = None

def _load_compressor():
    global _compressor
    if _compressor is None:
        logger.info("Loading LLMLingua compressor")
        # Using LLMLingua-2 for smaller footprint and faster CPU inference
        _compressor = PromptCompressor(
            model_name="microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
            use_llmlingua2=True
        )
    return _compressor

async def compress_context(query: str, chunks: list[str], target_ratio: float = 0.5) -> str:
    """Compress retrieved chunks by filtering non-essential tokens."""
    if not chunks:
        return ""
        
    def _compute():
        compressor = _load_compressor()
        concatenated_context = "\n\n".join(chunks)
        target_tokens = max(50, int(len(concatenated_context.split()) * target_ratio))
        
        result = compressor.compress_prompt(
            context=chunks,
            instruction="",
            question=query,
            target_token=target_tokens,
            rank_method="longllmlingua",
        )
        return result["compressed_prompt"]

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _compute)