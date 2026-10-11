from __future__ import annotations
from pydantic import BaseModel, EmailStr, Field

class UserRegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100, pattern='^[a-zA-Z0-9_-]+$')
    password: str = Field(..., min_length=8, max_length=128)
    model_config = {'json_schema_extra': {'examples': [{'email': 'user@example.com', 'username': 'johndoe', 'password': 'SecurePass123!'}]}}

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str
    model_config = {'json_schema_extra': {'examples': [{'email': 'user@example.com', 'password': 'SecurePass123!'}]}}

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'
    expires_in: int

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    is_active: bool
    model_config = {'from_attributes': True}
