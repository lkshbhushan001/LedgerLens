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
    questions = []
    ground_truths = []
    answers = []
    contexts_list = []
    
    for test in payload.test_cases:
        question = test["question"]
        expected = test.get("expected_answer", "")        
        
        req = QueryRequest(question=question, top_k=5)
        
        rag_response = await query_rag(user=admin, request=req)        
        
        questions.append(question)
        ground_truths.append(expected)
        answers.append(rag_response.answer)
        contexts_list.append([c.text for c in rag_response.sources])
    
    result = await run_evaluation_batch(
        questions=questions,
        contexts_list=contexts_list,
        answers=answers,
        ground_truths=ground_truths,
    )

    return result