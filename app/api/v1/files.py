from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.repositories.geo_file_repository import GeoFileRepository
from app.schemas.measurements import FileListItemSchema, FileUploadResponse, JobStatusResponse, MeasurementResultSchema, PaginatedFilesResponse, FeatureMeasurementSchema
from app.services.geo_file_service import GeoFileProcessingService
from app.services.measurement_service import MeasurementService
from app.services.report_service import ReportService
from app.services.storage_service import StorageService
router = APIRouter(prefix='/files', tags=['Files & Measurements'])

def _get_processing_service(db: AsyncSession=Depends(get_db)) -> GeoFileProcessingService:
    return GeoFileProcessingService(repo=GeoFileRepository(db), storage=StorageService(), measurement=MeasurementService())

@router.post('/upload', response_model=FileUploadResponse, status_code=status.HTTP_202_ACCEPTED, summary='Upload a GeoJSON, KML, or zipped Shapefile for measurement', responses={200: {'description': 'File processed synchronously'}, 202: {'description': 'File queued for async processing'}, 413: {'description': 'File too large'}, 422: {'description': 'Invalid or unsupported file'}})
async def upload_file(file: UploadFile=File(..., description='GeoJSON (.geojson/.json), KML (.kml), or zipped Shapefile (.zip)'), current_user: User=Depends(get_current_user), service: GeoFileProcessingService=Depends(_get_processing_service)) -> FileUploadResponse:
    content = await file.read()
    geo_file, is_async = await service.upload_and_process(file_content=content, original_filename=file.filename or 'upload', owner_id=current_user.id)
    return FileUploadResponse(file_id=geo_file.id, status='pending' if is_async else 'completed', job_id=geo_file.job_id if is_async else None, message='File queued for background processing. Poll GET /jobs/{job_id} for status.' if is_async else 'File processed successfully. Use GET /files/{id}/measurements to retrieve results.')

@router.get('/{file_id}/measurements', response_model=MeasurementResultSchema, summary='Get measurement results for an uploaded file')
async def get_measurements(file_id: str, unit: str | None=Query(None, description='Area unit: m2, km2, ha, acre'), length_unit: str | None=Query(None, description='Length unit: m, km, mi, ft'), current_user: User=Depends(get_current_user), service: GeoFileProcessingService=Depends(_get_processing_service)) -> MeasurementResultSchema:
    return await service.get_measurements(file_id=file_id, owner_id=current_user.id, area_unit=unit, length_unit=length_unit)

@router.get('/{file_id}/features', response_model=list[FeatureMeasurementSchema], summary='Get per-feature measurement breakdown')
async def get_features(file_id: str, current_user: User=Depends(get_current_user), service: GeoFileProcessingService=Depends(_get_processing_service)) -> list[FeatureMeasurementSchema]:
    return await service.get_features(file_id=file_id, owner_id=current_user.id)

@router.get('/{file_id}/geojson', summary='Get GeoJSON FeatureCollection for map rendering')
async def get_geojson(file_id: str, current_user: User=Depends(get_current_user), service: GeoFileProcessingService=Depends(_get_processing_service)) -> dict:
    return await service.get_geojson(file_id=file_id, owner_id=current_user.id)

@router.get('/{file_id}/report.pdf', summary='Download a PDF measurement report', response_class=Response)
async def download_report(file_id: str, current_user: User=Depends(get_current_user), service: GeoFileProcessingService=Depends(_get_processing_service)) -> Response:
    result = await service.get_measurements(file_id=file_id, owner_id=current_user.id)
    report_svc = ReportService()
    pdf_bytes = report_svc.generate(result)
    return Response(content=pdf_bytes, media_type='application/pdf', headers={'Content-Disposition': f'attachment; filename="report_{file_id}.pdf"'})

@router.delete('/{file_id}', status_code=status.HTTP_204_NO_CONTENT, response_model=None, summary='Delete a file and all its measurement data')
async def delete_file(file_id: str, current_user: User=Depends(get_current_user), service: GeoFileProcessingService=Depends(_get_processing_service)) -> None:
    await service.delete_file(file_id=file_id, owner_id=current_user.id)

@router.get('', response_model=PaginatedFilesResponse, summary='List uploaded files (paginated history)')
async def list_files(page: int=Query(1, ge=1, description='Page number'), page_size: int=Query(20, ge=1, le=100, description='Items per page'), status_filter: str | None=Query(None, alias='status'), format_filter: str | None=Query(None, alias='format'), current_user: User=Depends(get_current_user), db: AsyncSession=Depends(get_db)) -> PaginatedFilesResponse:
    repo = GeoFileRepository(db)
    files, total = await repo.list_by_owner(owner_id=current_user.id, page=page, page_size=page_size, status_filter=status_filter, format_filter=format_filter)
    items = []
    for f in files:
        feat_count = None
        area = None
        if f.measurement_result:
            feat_count = f.measurement_result.get('feature_count')
            area = f.measurement_result.get('total_area_m2')
        items.append(FileListItemSchema(id=f.id, original_filename=f.original_filename, file_format=f.file_format.value, file_size_bytes=f.file_size_bytes, status=f.status.value, feature_count=feat_count, total_area_m2=area, created_at=f.created_at.isoformat()))
    import math
    return PaginatedFilesResponse(items=items, total=total, page=page, page_size=page_size, pages=math.ceil(total / page_size) if total else 1)
