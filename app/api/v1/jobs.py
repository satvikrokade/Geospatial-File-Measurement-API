from __future__ import annotations
from fastapi import APIRouter, Depends
from app.auth.dependencies import get_current_user
from app.core.exceptions import JobNotFoundError
from app.models.user import User
from app.schemas.measurements import JobStatusResponse
router = APIRouter(prefix='/jobs', tags=['Background Jobs'])

@router.get('/{job_id}', response_model=JobStatusResponse, summary='Check background job processing status')
async def get_job_status(job_id: str, current_user: User=Depends(get_current_user)) -> JobStatusResponse:
    try:
        from arq.connections import RedisSettings
        import arq
        from app.core.config import get_settings
        settings = get_settings()
        redis_settings = RedisSettings.from_dsn(settings.redis_url)
        pool = await arq.create_pool(redis_settings)
        job = arq.Job(job_id=job_id, redis=pool)
        job_info = await job.info()
        await pool.aclose()
        if job_info is None:
            raise JobNotFoundError(f"Job '{job_id}' not found")
        status_map = {'queued': 'pending', 'in_progress': 'processing', 'complete': 'completed', 'failed': 'failed', 'not_found': 'not_found'}
        arq_status = str(job_info.status).split('.')[-1].lower()
        mapped_status = status_map.get(arq_status, arq_status)
        file_id = None
        message = None
        if job_info.result and isinstance(job_info.result, dict):
            file_id = job_info.result.get('file_id')
            message = job_info.result.get('error')
        return JobStatusResponse(job_id=job_id, status=mapped_status, file_id=file_id, message=message)
    except JobNotFoundError:
        raise
    except Exception as exc:
        return JobStatusResponse(job_id=job_id, status='unknown', message=f'Could not retrieve job status: {exc}')
