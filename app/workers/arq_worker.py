from __future__ import annotations
import uuid
from pathlib import Path
from typing import Any
import arq
from arq import ArqRedis
from arq.connections import RedisSettings
from app.core.config import get_settings
from app.core.logging import get_logger, configure_logging
_logger = get_logger(__name__)
_settings = get_settings()

async def process_geo_file(ctx: dict[str, Any], file_id: str) -> dict[str, Any]:
    configure_logging(_settings.log_level, _settings.log_json)
    _logger.info('worker_starting_job', file_id=file_id)
    try:
        from app.database.session import AsyncSessionLocal
        from app.repositories.geo_file_repository import GeoFileRepository
        from app.services.measurement_service import MeasurementService
        from app.services.parsers import default_parser_factory
        from app.models.geo_file import ProcessingStatus
        async with AsyncSessionLocal() as db:
            repo = GeoFileRepository(db)
            geo_file = await repo.get_by_id(file_id)
            if not geo_file:
                _logger.error('worker_file_not_found', file_id=file_id)
                return {'status': 'failed', 'error': 'File not found'}
            stored_path = Path(geo_file.file_path)
            extension = Path(geo_file.stored_filename).suffix.lower()
            await repo.update_status(file_id, ProcessingStatus.PROCESSING)
            await db.commit()
            parser = default_parser_factory.get_parser(extension)
            gdf, crs_str = parser.parse(stored_path)
            measurement_svc = MeasurementService()
            result, feature_results = measurement_svc.measure(gdf=gdf, source_crs_str=crs_str, file_id=file_id, filename=geo_file.original_filename, file_format=geo_file.file_format.value)
            result_dict = result.model_dump()
            await repo.update_measurement_result(file_id, result_dict)
            from app.models.geo_file import GeoFeature
            from pyproj import CRS, Transformer
            from shapely.ops import transform
            db_features: list[GeoFeature] = []
            src_crs = CRS.from_user_input(crs_str)
            wgs84 = CRS.from_epsg(4326)
            for i, (fm, (_, row)) in enumerate(zip(feature_results, gdf.iterrows())):
                try:
                    geom = row.geometry
                    if src_crs != wgs84:
                        transformer = Transformer.from_crs(src_crs, wgs84, always_xy=True)
                        geom = transform(transformer.transform, geom)
                    db_feat = GeoFeature(geo_file_id=file_id, feature_index=i, geometry_type=fm.geometry_type, properties=fm.properties, measurements=fm.model_dump(), warnings=fm.warnings if fm.warnings else None, geometry=f'SRID=4326;{geom.wkt}')
                    db_features.append(db_feat)
                except Exception as exc:
                    _logger.warning('worker_feature_persist_failed', index=i, error=str(exc))
            if db_features:
                await repo.save_features(db_features)
            await db.commit()
        _logger.info('worker_job_complete', file_id=file_id)
        return {'status': 'completed', 'file_id': file_id}
    except Exception as exc:
        _logger.exception('worker_job_failed', file_id=file_id, error=str(exc))
        try:
            from app.database.session import AsyncSessionLocal
            from app.repositories.geo_file_repository import GeoFileRepository
            from app.models.geo_file import ProcessingStatus
            async with AsyncSessionLocal() as db:
                repo = GeoFileRepository(db)
                await repo.update_status(file_id, ProcessingStatus.FAILED, error_message=str(exc))
                await db.commit()
        except Exception:
            pass
        return {'status': 'failed', 'error': str(exc)}

async def enqueue_process_file(file_id: str) -> str:
    redis_url = _settings.redis_url
    redis_settings = RedisSettings.from_dsn(redis_url)
    pool: ArqRedis = await arq.create_pool(redis_settings)
    job = await pool.enqueue_job('process_geo_file', file_id)
    await pool.aclose()
    if job is None:
        return str(uuid.uuid4())
    return job.job_id

class WorkerSettings:
    functions = [process_geo_file]
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
    max_jobs = 10
    job_timeout = 300
    keep_result = 3600
    retry_jobs = True
    max_tries = 3
