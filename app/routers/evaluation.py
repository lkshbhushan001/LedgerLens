from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.core.security import require_admin
from app.models.schemas import EvaluationResult, UserIdentity
from app.routers.query import query_rag
from app.models.schemas import QueryRequest
from app.services.evaluation import run_evaluation_batch

router = APIRouter(prefix="/evaluate", tags=["evaluation"])

class EvaluationRequest(BaseModel):
    """Payload containing ground-truth Q&A pairs for the harness."""
    test_cases: list[dict[str, str]]  # list of {"question": "...", "expected_answer": "..."}

@router.post(
    "/run",
    status_code=status.HTTP_200_OK,
    response_model=EvaluationResult,
    summary="Run the Ragas evaluation harness (Admin Only)",
)
async def trigger_evaluation(
    admin: Annotated[UserIdentity, Depends(require_admin)],
    payload: EvaluationRequest,
) -> EvaluationResult:
    """
    Executes the full RAG pipeline for a set of test cases, collects the contexts
    and generated answers, and passes them to the Ragas evaluator.
    Requires an Admin JWT token.
    """
    questions = []
    ground_truths = []
    answers = []
    contexts_list = []

    # 1. Run the RAG pipeline for each test case to gather artifacts
    for test in payload.test_cases:
        question = test["question"]
        expected = test.get("expected_answer", "")
        
        # We pass the Admin user object directly into the RAG pipeline
        req = QueryRequest(question=question, top_k=5)
        
        rag_response = await query_rag(user=admin, request=req)
        
        # Extract artifacts
        questions.append(question)
        ground_truths.append(expected)
        answers.append(rag_response.answer)
        contexts_list.append([c.text for c in rag_response.sources])

    # 2. Feed the artifacts into the Evaluation Harness
    result = await run_evaluation_batch(
        questions=questions,
        contexts_list=contexts_list,
        answers=answers,
        ground_truths=ground_truths,
    )

    return result