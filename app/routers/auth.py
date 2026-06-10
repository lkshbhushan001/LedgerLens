
from fastapi import APIRouter, status
from pydantic import BaseModel

from app.core.security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

class TokenRequest(BaseModel):    
    user_id: str
    email: str
    permission_groups: list[str]  # e.g., ["analyst", "fund-a"]
    is_admin: bool = False

class TokenResponse(BaseModel):    
    access_token: str
    token_type: str = "bearer"

@router.post(
    "/token", 
    status_code=status.HTTP_200_OK, 
    response_model=TokenResponse,
    summary="Mint a test JWT with custom roles"
)
async def login_for_access_token(req: TokenRequest) -> TokenResponse:
    
    token = create_access_token(
        user_id=req.user_id,
        email=req.email,
        permission_groups=req.permission_groups,
        is_admin=req.is_admin
    )
    return TokenResponse(access_token=token)