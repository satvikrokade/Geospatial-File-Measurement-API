from __future__ import annotations
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.database.session import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository
_bearer = HTTPBearer(auto_error=False)

async def get_current_user(credentials: HTTPAuthorizationCredentials | None=Depends(_bearer), db: AsyncSession=Depends(get_db)) -> User:
    if not credentials:
        raise UnauthorizedError('Missing Bearer token')
    payload = decode_token(credentials.credentials, expected_type='access')
    user_id: str = payload['sub']
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise UnauthorizedError('User not found')
    if not user.is_active:
        raise ForbiddenError('Account is disabled')
    return user

async def get_current_superuser(current_user: User=Depends(get_current_user)) -> User:
    if not current_user.is_superuser:
        raise ForbiddenError('Superuser access required')
    return current_user
