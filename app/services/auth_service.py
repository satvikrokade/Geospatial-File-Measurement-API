from __future__ import annotations
from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, needs_rehash, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse, UserRegisterRequest

class AuthService:

    def __init__(self, user_repo: UserRepository) -> None:
        self._repo = user_repo

    async def register(self, data: UserRegisterRequest) -> User:
        if await self._repo.get_by_email(data.email):
            raise ValueError(f"Email '{data.email}' is already registered")
        if await self._repo.get_by_username(data.username):
            raise ValueError(f"Username '{data.username}' is already taken")
        hashed = hash_password(data.password)
        return await self._repo.create(email=data.email, username=data.username, hashed_password=hashed)

    async def login(self, email: str, password: str) -> TokenResponse:
        user = await self._repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedError('Invalid email or password')
        if not user.is_active:
            raise UnauthorizedError('Account is disabled')
        if needs_rehash(user.hashed_password):
            new_hash = hash_password(password)
            await self._repo.update_password(user, new_hash)
        settings = get_settings()
        return TokenResponse(access_token=create_access_token(user.id), refresh_token=create_refresh_token(user.id), token_type='bearer', expires_in=settings.access_token_expire_minutes * 60)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token, expected_type='refresh')
        user_id = payload['sub']
        user = await self._repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise UnauthorizedError('User not found or disabled')
        settings = get_settings()
        return TokenResponse(access_token=create_access_token(user_id), refresh_token=create_refresh_token(user_id), token_type='bearer', expires_in=settings.access_token_expire_minutes * 60)
