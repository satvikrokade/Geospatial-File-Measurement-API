from __future__ import annotations
import pathlib
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestIDMiddleware, SecurityHeadersMiddleware, TimingMiddleware
settings = get_settings()
configure_logging(settings.log_level, settings.log_json)
_logger = get_logger(__name__)
limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    _logger.info('application_startup', env=settings.app_env, upload_dir=str(settings.upload_dir))
    yield
    _logger.info('application_shutdown')

def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version='1.0.0', description='Production-grade Geospatial File Measurement API. Upload GeoJSON, KML, or zipped Shapefiles and receive accurate area, perimeter, centroid, bounding box, and statistical measurements. \n\n**Measurement method**: Geodesic calculations on the WGS84 ellipsoid using pyproj.Geod — never raw degree-based approximations.', openapi_url=f'{settings.api_v1_prefix}/openapi.json', docs_url=f'{settings.api_v1_prefix}/docs', redoc_url=f'{settings.api_v1_prefix}/redoc', lifespan=lifespan, contact={'name': 'Geospatial API', 'email': 'api@geospatial.example.com'}, license_info={'name': 'MIT'})
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=['*'], allow_headers=['*'], expose_headers=['X-Request-ID', 'X-Process-Time'])
    register_exception_handlers(app)
    from app.api.v1.auth import router as auth_router
    from app.api.v1.files import router as files_router
    from app.api.v1.jobs import router as jobs_router
    from app.api.v1.health import router as health_router
    from app.api.v1.map import router as map_router
    prefix = settings.api_v1_prefix
    app.include_router(health_router)
    app.include_router(auth_router, prefix=prefix)
    app.include_router(files_router, prefix=prefix)
    app.include_router(jobs_router, prefix=prefix)
    app.include_router(map_router, prefix=prefix)
    static_dir = pathlib.Path(__file__).parent / 'static'
    static_dir.mkdir(exist_ok=True)
    app.mount('/static', StaticFiles(directory=str(static_dir)), name='static')
    _logger.info('routes_registered', route_count=len(app.routes))
    return app
app = create_app()
