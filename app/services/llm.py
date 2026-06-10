import json
import logging
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.config import settings

logger = logging.getLogger(__name__)

groq_client = AsyncOpenAI(
    api_key=settings.GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def _call_router_llm(prompt: str, query: str):
    """Raw LLM call with retry logic for decomposition."""
    return await groq_client.chat.completions.create(
        model=settings.ROUTER_MODEL,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": query}
        ],
        temperature=0.0,
    )

async def decompose_query(query: str) -> list[str]:
    # Break a complex query into atomic sub-queries for parallel vector search.
    system_prompt = (
        "You are an expert financial query router. "
        "Decompose the following complex user question into 1 to 3 distinct, atomic sub-questions "
        "optimized for semantic vector search. If the question is already simple, return it as a single item. "
        "Respond ONLY with a JSON object containing a 'sub_queries' key mapped to a list of strings."
    )
    
    try:
        response = await _call_router_llm(system_prompt, query)
        content = response.choices[0].message.content
        if not isinstance(content, str):
            content = str(content)

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            import re
            match = re.search(r"\{.*\}", content, re.S)
            if match:
                data = json.loads(match.group(0))
            else:
                raise

        queries = data.get("sub_queries")
        if isinstance(queries, str):
            queries = [queries]
        if not isinstance(queries, list):
            queries = [query]

        queries = [q.strip() for q in queries if isinstance(q, str) and q.strip()]
        if not queries:
            queries = [query]

        logger.info("Decomposed query '%s' into %d sub-queries", query[:30], len(queries))
        return queries

    except Exception as exc:
        logger.warning("Query decomposition failed after retries, falling back to original query: %s", exc)
        return [query]

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def generate_answer(query: str, context: str) -> str:
    # Generate the final answer using the highly compressed context
    prompt = (
        "You are an expert financial analyst AI. Answer the user's question strictly using the provided context. "
        "If the context does not contain the answer, explicitly state that you do not have enough information.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}"
    )
    
    response = await groq_client.chat.completions.create(
        model=settings.SYNTHESIS_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    return response.choices[0].message.content

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def _call_vision_llm(prompt: str, base64_image: str):    
    return await groq_client.chat.completions.create(
        model=settings.VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        temperature=0.1,
        max_tokens=500,
    )

async def generate_image_description(base64_image: str) -> str:
    # Analyze an extracted image chart/graph and return a dense description
    prompt = (
        "You are an expert financial data analyst. Analyze this image (which may be a chart, "
        "graph, or table). Provide a dense, highly detailed text description summarizing the axes, "
        "trends, key data points, and any notable anomalies. Do not include introductory fluff."
    )
    
    try:
        response = await _call_vision_llm(prompt, base64_image)
        return response.choices[0].message.content
    except Exception as exc:
        logger.error("Vision LLM failed to generate description after retries: %s", exc)
        return "Image description unavailable."