from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import get_current_user
from app.core.exceptions import UnauthorizedError
from app.database.session import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RefreshTokenRequest, TokenResponse, UserLoginRequest, UserRegisterRequest, UserResponse
from app.services.auth_service import AuthService
router = APIRouter(prefix='/auth', tags=['Authentication'])

def _get_auth_service(db: AsyncSession=Depends(get_db)) -> AuthService:
    return AuthService(UserRepository(db))

@router.post('/register', response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary='Register a new user account', responses={409: {'description': 'Email or username already exists'}})
async def register(body: UserRegisterRequest, service: AuthService=Depends(_get_auth_service)) -> UserResponse:
    try:
        user = await service.register(body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return UserResponse.model_validate(user)

@router.post('/login', response_model=TokenResponse, summary='Login and receive JWT token pair', responses={401: {'description': 'Invalid credentials'}})
async def login(body: UserLoginRequest, service: AuthService=Depends(_get_auth_service)) -> TokenResponse:
    return await service.login(body.email, body.password)

@router.post('/refresh', response_model=TokenResponse, summary='Refresh access token using refresh token')
async def refresh_token(body: RefreshTokenRequest, service: AuthService=Depends(_get_auth_service)) -> TokenResponse:
    return await service.refresh(body.refresh_token)

@router.get('/me', response_model=UserResponse, summary='Get current authenticated user profile')
async def me(current_user: User=Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)
