"""Groq LLM integrations for routing and synthesis."""

import json
import logging
from openai import AsyncOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize OpenAI client with Groq's endpoint
groq_client = AsyncOpenAI(
    api_key=settings.GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

async def decompose_query(query: str) -> list[str]:
    """Router: Break a complex query into atomic sub-queries for parallel vector search."""
    system_prompt = (
        "You are an expert financial query router. "
        "Decompose the following complex user question into 1 to 3 distinct, atomic sub-questions "
        "optimized for semantic vector search. If the question is already simple, return it as a single item. "
        "Respond ONLY with a JSON object containing a 'sub_queries' key mapped to a list of strings."
    )
    
    try:
        response = await groq_client.chat.completions.create(
            model=settings.ROUTER_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        queries = data.get("sub_queries", [query])
        
        logger.info("Decomposed query '%s' into %d sub-queries", query[:30], len(queries))
        return queries
    except Exception as exc:
        logger.warning("Query decomposition failed, falling back to original query: %s", exc)
        return [query]

async def generate_answer(query: str, context: str) -> str:
    """Synthesis: Generate the final answer using the highly compressed context."""
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

async def generate_image_description(base64_image: str) -> str:
    """Vision: Analyze an extracted image chart/graph and return a dense description."""
    prompt = (
        "You are an expert financial data analyst. Analyze this image (which may be a chart, "
        "graph, or table). Provide a dense, highly detailed text description summarizing the axes, "
        "trends, key data points, and any notable anomalies. Do not include introductory fluff."
    )
    
    try:
        response = await groq_client.chat.completions.create(
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
        return response.choices[0].message.content
    except Exception as exc:
        logger.error("Vision LLM failed to generate description: %s", exc)
        return "Image description unavailable."