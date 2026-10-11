from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.services.geo_file_service import GeoFileProcessingService
from app.services.measurement_service import MeasurementService
from app.services.storage_service import StorageService
from app.repositories.geo_file_repository import GeoFileRepository
from app.database.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
import pathlib
router = APIRouter(tags=['Map'])
_TEMPLATE_DIR = pathlib.Path(__file__).parent.parent.parent / 'templates'
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

def _get_service(db: AsyncSession=Depends(get_db)) -> GeoFileProcessingService:
    return GeoFileProcessingService(repo=GeoFileRepository(db), storage=StorageService(), measurement=MeasurementService())

@router.get('/map/{file_id}', response_class=HTMLResponse, summary='Interactive Leaflet map preview for an uploaded file', include_in_schema=False)
async def map_view(file_id: str, request: Request, current_user: User=Depends(get_current_user), service: GeoFileProcessingService=Depends(_get_service)) -> HTMLResponse:
    result = await service.get_measurements(file_id=file_id, owner_id=current_user.id)
    geojson = await service.get_geojson(file_id=file_id, owner_id=current_user.id)
    return templates.TemplateResponse('map.html', {'request': request, 'file_id': file_id, 'filename': result.filename, 'format': result.format, 'feature_count': result.feature_count, 'source_crs': result.source_crs, 'calculation_method': result.calculation_method, 'total_area_m2': result.total_area_m2, 'total_perimeter_m': result.total_perimeter_m, 'centroid': result.centroid_wgs84, 'bbox': result.bounding_box, 'warnings': result.warnings, 'geojson': geojson})
