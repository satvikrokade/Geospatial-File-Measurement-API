from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import geopandas as gpd
from geoalchemy2.shape import from_shape
from shapely.ops import unary_union
from app.core.config import get_settings
from app.core.exceptions import ForbiddenError, InvalidFileError, ProcessingError, ResourceNotFoundError
from app.core.logging import get_logger
from app.models.geo_file import GeoFeature, GeoFile, ProcessingStatus
from app.repositories.geo_file_repository import GeoFileRepository
from app.schemas.measurements import FeatureMeasurementSchema, MeasurementResultSchema
from app.services.measurement_service import MeasurementService
from app.services.parsers import default_parser_factory
from app.services.storage_service import StorageService
from app.services.unit_converter import AreaUnit, LengthUnit, UnitConverter
_logger = get_logger(__name__)
_settings = get_settings()

class GeoFileProcessingService:

    def __init__(self, repo: GeoFileRepository, storage: StorageService, measurement: MeasurementService) -> None:
        self._repo = repo
        self._storage = storage
        self._measurement = measurement

    async def upload_and_process(self, file_content: bytes, original_filename: str, owner_id: str) -> tuple[GeoFile, bool]:
        stored_name, stored_path, extension = self._storage.validate_and_store(file_content, original_filename)
        format_map = {'.geojson': 'geojson', '.json': 'geojson', '.kml': 'kml', '.zip': 'shapefile'}
        geo_file = await self._repo.create(owner_id=owner_id, original_filename=original_filename, stored_filename=stored_name, file_format=format_map[extension], file_size_bytes=len(file_content), file_path=str(stored_path))
        is_async = len(file_content) > _settings.async_threshold_bytes
        if is_async:
            job_id = await self._enqueue_processing(geo_file.id)
            await self._repo.update_status(geo_file.id, ProcessingStatus.PENDING, job_id=job_id)
            geo_file.job_id = job_id
            return (geo_file, True)
        else:
            try:
                await self._process_file(geo_file.id, stored_path, extension, original_filename)
            except Exception as exc:
                await self._repo.update_status(geo_file.id, ProcessingStatus.FAILED, error_message=str(exc))
                raise
            return (geo_file, False)

    async def get_measurements(self, file_id: str, owner_id: str, area_unit: str | None=None, length_unit: str | None=None) -> MeasurementResultSchema:
        geo_file = await self._repo.get_by_id_with_owner_check(file_id, owner_id)
        if not geo_file:
            raise ResourceNotFoundError(f"File '{file_id}' not found")
        if geo_file.status == ProcessingStatus.PENDING:
            raise ProcessingError('File is still queued for processing', details={'file_id': file_id})
        if geo_file.status == ProcessingStatus.PROCESSING:
            raise ProcessingError('File is currently being processed', details={'file_id': file_id})
        if geo_file.status == ProcessingStatus.FAILED:
            raise ProcessingError(f'Processing failed: {geo_file.error_message}', details={'file_id': file_id})
        if not geo_file.measurement_result:
            raise ProcessingError('No measurement results available', details={'file_id': file_id})
        result = MeasurementResultSchema.model_validate(geo_file.measurement_result)
        if area_unit and result.total_area_m2 is not None:
            result.area_converted = round(UnitConverter.convert_area(result.total_area_m2, area_unit), 6)
            result.area_unit = UnitConverter.area_unit_label(area_unit)
        if length_unit and result.total_perimeter_m is not None:
            result.perimeter_converted = round(UnitConverter.convert_length(result.total_perimeter_m, length_unit), 6)
            result.perimeter_unit = UnitConverter.length_unit_label(length_unit)
        return result

    async def get_features(self, file_id: str, owner_id: str) -> list[FeatureMeasurementSchema]:
        geo_file = await self._repo.get_by_id_with_owner_check(file_id, owner_id)
        if not geo_file:
            raise ResourceNotFoundError(f"File '{file_id}' not found")
        db_features = await self._repo.get_features(file_id)
        return [FeatureMeasurementSchema.model_validate(f.measurements) for f in db_features if f.measurements]

    async def get_geojson(self, file_id: str, owner_id: str) -> dict[str, Any]:
        geo_file = await self._repo.get_by_id_with_owner_check(file_id, owner_id)
        if not geo_file:
            raise ResourceNotFoundError(f"File '{file_id}' not found")
        db_features = await self._repo.get_features(file_id)
        features = []
        for f in db_features:
            try:
                from geoalchemy2.shape import to_shape
                geom = to_shape(f.geometry)
                from shapely.geometry import mapping
                geom_dict = mapping(geom)
            except Exception:
                geom_dict = None
            features.append({'type': 'Feature', 'geometry': geom_dict, 'properties': {**(f.properties or {}), '_feature_index': f.feature_index, '_geometry_type': f.geometry_type, **(f.measurements or {})}})
        return {'type': 'FeatureCollection', 'features': features}

    async def delete_file(self, file_id: str, owner_id: str) -> None:
        geo_file = await self._repo.get_by_id_with_owner_check(file_id, owner_id)
        if not geo_file:
            raise ResourceNotFoundError(f"File '{file_id}' not found")
        self._storage.delete_file(geo_file.stored_filename)
        await self._repo.delete(file_id, owner_id)

    async def _process_file(self, file_id: str, file_path: Path, extension: str, original_filename: str) -> None:
        await self._repo.update_status(file_id, ProcessingStatus.PROCESSING)
        try:
            parser = default_parser_factory.get_parser(extension)
            gdf, crs_str = parser.parse(file_path)
            result, feature_results = self._measurement.measure(gdf=gdf, source_crs_str=crs_str, file_id=file_id, filename=original_filename, file_format=extension.lstrip('.'))
            union_geom = None
            try:
                geoms = [row.geometry for _, row in gdf.iterrows() if row.geometry and (not row.geometry.is_empty)]
                if geoms:
                    union_geom = unary_union(geoms)
                    from geoalchemy2 import WKBElement
                    from shapely import wkb
                    union_wkb = union_geom.wkb_hex
            except Exception as exc:
                _logger.warning('union_geometry_failed', file_id=file_id, error=str(exc))
                union_wkb = None
            result_dict = result.model_dump()
            await self._repo.update_measurement_result(file_id, result_dict, geometry_wkb=None)
            db_features: list[GeoFeature] = []
            for i, (fm, (_, row)) in enumerate(zip(feature_results, gdf.iterrows())):
                try:
                    geom = row.geometry
                    from pyproj import CRS, Transformer
                    from shapely.ops import transform
                    src_crs = CRS.from_user_input(crs_str)
                    wgs84 = CRS.from_epsg(4326)
                    if src_crs != wgs84:
                        transformer = Transformer.from_crs(src_crs, wgs84, always_xy=True)
                        geom = transform(transformer.transform, geom)
                    db_feat = GeoFeature(geo_file_id=file_id, feature_index=i, geometry_type=fm.geometry_type, properties=fm.properties, measurements=fm.model_dump(), warnings=fm.warnings if fm.warnings else None, geometry=f'SRID=4326;{geom.wkt}')
                    db_features.append(db_feat)
                except Exception as exc:
                    _logger.warning('feature_persist_failed', file_id=file_id, feature_index=i, error=str(exc))
            if db_features:
                await self._repo.save_features(db_features)
            from sqlalchemy import update
            _logger.info('file_processing_complete', file_id=file_id)
        except Exception as exc:
            await self._repo.update_status(file_id, ProcessingStatus.FAILED, error_message=str(exc))
            raise

    async def _enqueue_processing(self, file_id: str) -> str:
        try:
            from app.workers.arq_worker import enqueue_process_file
            job_id = await enqueue_process_file(file_id)
            return job_id
        except Exception as exc:
            _logger.warning('arq_enqueue_failed', file_id=file_id, error=str(exc))
            return f'sync_{file_id}'
