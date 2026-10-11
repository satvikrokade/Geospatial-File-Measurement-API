from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError
_ph = PasswordHasher()

def hash_password(plain: str) -> str:
    return _ph.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False

def needs_rehash(hashed: str) -> bool:
    return _ph.check_needs_rehash(hashed)
_TokenPayload = dict[str, Any]

def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)

def create_access_token(subject: str, extra: _TokenPayload | None=None) -> str:
    settings = get_settings()
    expire = _utc_now() + timedelta(minutes=settings.access_token_expire_minutes)
    payload: _TokenPayload = {'sub': subject, 'exp': expire, 'iat': _utc_now(), 'type': 'access', **(extra or {})}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)

def create_refresh_token(subject: str) -> str:
    settings = get_settings()
    expire = _utc_now() + timedelta(days=settings.refresh_token_expire_days)
    payload: _TokenPayload = {'sub': subject, 'exp': expire, 'iat': _utc_now(), 'type': 'refresh'}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)

def decode_token(token: str, expected_type: str='access') -> _TokenPayload:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError('Token has expired')
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError(f'Invalid token: {exc}')
    if payload.get('type') != expected_type:
        raise UnauthorizedError(f'Expected {expected_type} token')
    return payload
