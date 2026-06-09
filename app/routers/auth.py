"""Authentication router for issuing JWTs."""

from fastapi import APIRouter, status
from pydantic import BaseModel

from app.core.security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

class TokenRequest(BaseModel):
    """Payload for requesting a test JWT."""
    user_id: str
    email: str
    permission_groups: list[str]  # e.g., ["analyst", "fund-a"]
    is_admin: bool = False

class TokenResponse(BaseModel):
    """Returned OAuth2 compliant bearer token."""
    access_token: str
    token_type: str = "bearer"

@router.post(
    "/token", 
    status_code=status.HTTP_200_OK, 
    response_model=TokenResponse,
    summary="Mint a test JWT with custom roles"
)
async def login_for_access_token(req: TokenRequest) -> TokenResponse:
    """
    Generate a JWT containing specific roles. 
    (Note: In a production environment, this would require a password/SSO validation).
    """
    token = create_access_token(
        user_id=req.user_id,
        email=req.email,
        permission_groups=req.permission_groups,
        is_admin=req.is_admin
    )
    return TokenResponse(access_token=token)