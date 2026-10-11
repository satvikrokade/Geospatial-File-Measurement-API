from __future__ import annotations
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
class TestAuthRegister:

    async def test_register_success(self, client: AsyncClient) -> None:
        resp = await client.post('/api/v1/auth/register', json={'email': 'test@example.com', 'username': 'testuser', 'password': 'SecurePass123!'})
        assert resp.status_code == 201
        data = resp.json()
        assert data['email'] == 'test@example.com'
        assert data['username'] == 'testuser'
        assert 'id' in data
        assert 'hashed_password' not in data

    async def test_register_duplicate_email(self, client: AsyncClient) -> None:
        payload = {'email': 'dup@example.com', 'username': 'dupuser', 'password': 'SecurePass123!'}
        await client.post('/api/v1/auth/register', json=payload)
        resp = await client.post('/api/v1/auth/register', json={**payload, 'username': 'dupuser2'})
        assert resp.status_code == 409

    async def test_register_duplicate_username(self, client: AsyncClient) -> None:
        await client.post('/api/v1/auth/register', json={'email': 'user1@ex.com', 'username': 'samename', 'password': 'Pass123!'})
        resp = await client.post('/api/v1/auth/register', json={'email': 'user2@ex.com', 'username': 'samename', 'password': 'Pass123!'})
        assert resp.status_code == 409

    async def test_register_weak_password_rejected(self, client: AsyncClient) -> None:
        resp = await client.post('/api/v1/auth/register', json={'email': 'weak@example.com', 'username': 'weakuser', 'password': 'short'})
        assert resp.status_code == 422

    async def test_register_invalid_email(self, client: AsyncClient) -> None:
        resp = await client.post('/api/v1/auth/register', json={'email': 'not-an-email', 'username': 'user123', 'password': 'SecurePass123!'})
        assert resp.status_code == 422

@pytest.mark.asyncio
class TestAuthLogin:

    @pytest.fixture(autouse=True)
    async def create_user(self, client: AsyncClient) -> None:
        await client.post('/api/v1/auth/register', json={'email': 'login@example.com', 'username': 'loginuser', 'password': 'LoginPass123!'})

    async def test_login_success(self, client: AsyncClient) -> None:
        resp = await client.post('/api/v1/auth/login', json={'email': 'login@example.com', 'password': 'LoginPass123!'})
        assert resp.status_code == 200
        data = resp.json()
        assert 'access_token' in data
        assert 'refresh_token' in data
        assert data['token_type'] == 'bearer'

    async def test_login_wrong_password(self, client: AsyncClient) -> None:
        resp = await client.post('/api/v1/auth/login', json={'email': 'login@example.com', 'password': 'wrongpassword'})
        assert resp.status_code == 401
        assert resp.json()['error']['code'] == 'unauthorized'

    async def test_login_unknown_email(self, client: AsyncClient) -> None:
        resp = await client.post('/api/v1/auth/login', json={'email': 'nobody@example.com', 'password': 'SomePass123!'})
        assert resp.status_code == 401

@pytest.mark.asyncio
class TestAuthMe:

    async def _get_token(self, client: AsyncClient, email: str, username: str) -> str:
        await client.post('/api/v1/auth/register', json={'email': email, 'username': username, 'password': 'TestPass123!'})
        resp = await client.post('/api/v1/auth/login', json={'email': email, 'password': 'TestPass123!'})
        return resp.json()['access_token']

    async def test_me_authenticated(self, client: AsyncClient) -> None:
        token = await self._get_token(client, 'me@example.com', 'meuser')
        resp = await client.get('/api/v1/auth/me', headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code == 200
        assert resp.json()['email'] == 'me@example.com'

    async def test_me_unauthenticated(self, client: AsyncClient) -> None:
        resp = await client.get('/api/v1/auth/me')
        assert resp.status_code == 401

    async def test_me_invalid_token(self, client: AsyncClient) -> None:
        resp = await client.get('/api/v1/auth/me', headers={'Authorization': 'Bearer invalid.token.here'})
        assert resp.status_code == 401

@pytest.mark.asyncio
class TestTokenRefresh:

    async def test_refresh_returns_new_access_token(self, client: AsyncClient) -> None:
        await client.post('/api/v1/auth/register', json={'email': 'refresh@ex.com', 'username': 'refreshuser', 'password': 'Pass123!Pass'})
        login = await client.post('/api/v1/auth/login', json={'email': 'refresh@ex.com', 'password': 'Pass123!Pass'})
        refresh_token = login.json()['refresh_token']
        resp = await client.post('/api/v1/auth/refresh', json={'refresh_token': refresh_token})
        assert resp.status_code == 200
        assert 'access_token' in resp.json()

    async def test_refresh_with_access_token_fails(self, client: AsyncClient) -> None:
        await client.post('/api/v1/auth/register', json={'email': 'ref2@ex.com', 'username': 'ref2user', 'password': 'Pass123!Pass'})
        login = await client.post('/api/v1/auth/login', json={'email': 'ref2@ex.com', 'password': 'Pass123!Pass'})
        access_token = login.json()['access_token']
        resp = await client.post('/api/v1/auth/refresh', json={'refresh_token': access_token})
        assert resp.status_code == 401
