
from fastapi import APIRouter, status
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"


@router.get("/health", status_code=status.HTTP_200_OK, response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok")
