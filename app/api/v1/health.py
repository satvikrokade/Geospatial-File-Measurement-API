from __future__ import annotations
from fastapi import APIRouter
from sqlalchemy import text
router = APIRouter(tags=['Health'])

@router.get('/health', summary='Liveness check — is the API process running?')
async def health() -> dict:
    return {'status': 'ok', 'service': 'geospatial-api'}

@router.get('/ready', summary='Readiness check — are DB and Redis reachable?')
async def ready() -> dict:
    results: dict = {'status': 'ok', 'checks': {}}
    try:
        from app.database.session import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            await db.execute(text('SELECT 1'))
        results['checks']['database'] = 'ok'
    except Exception as exc:
        results['checks']['database'] = f'error: {exc}'
        results['status'] = 'degraded'
    try:
        import redis.asyncio as aioredis
        from app.core.config import get_settings
        settings = get_settings()
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        results['checks']['redis'] = 'ok'
    except Exception as exc:
        results['checks']['redis'] = f'error: {exc}'
        results['status'] = 'degraded'
    return results
