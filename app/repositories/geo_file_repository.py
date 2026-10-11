from __future__ import annotations
from typing import Any
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.geo_file import GeoFeature, GeoFile, ProcessingStatus

class GeoFileRepository:

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, *, owner_id: str, original_filename: str, stored_filename: str, file_format: str, file_size_bytes: int, file_path: str, source_crs: str | None=None) -> GeoFile:
        geo_file = GeoFile(owner_id=owner_id, original_filename=original_filename, stored_filename=stored_filename, file_format=file_format, file_size_bytes=file_size_bytes, file_path=file_path, source_crs=source_crs, status=ProcessingStatus.PENDING)
        self._db.add(geo_file)
        await self._db.flush()
        await self._db.refresh(geo_file)
        return geo_file

    async def get_by_id(self, file_id: str) -> GeoFile | None:
        result = await self._db.execute(select(GeoFile).where(GeoFile.id == file_id))
        return result.scalar_one_or_none()

    async def get_by_id_with_owner_check(self, file_id: str, owner_id: str) -> GeoFile | None:
        result = await self._db.execute(select(GeoFile).where(GeoFile.id == file_id, GeoFile.owner_id == owner_id))
        return result.scalar_one_or_none()

    async def get_features(self, file_id: str) -> list[GeoFeature]:
        result = await self._db.execute(select(GeoFeature).where(GeoFeature.geo_file_id == file_id).order_by(GeoFeature.feature_index))
        return list(result.scalars().all())

    async def list_by_owner(self, owner_id: str, page: int=1, page_size: int=20, status_filter: str | None=None, format_filter: str | None=None) -> tuple[list[GeoFile], int]:
        query = select(GeoFile).where(GeoFile.owner_id == owner_id)
        if status_filter:
            query = query.where(GeoFile.status == status_filter)
        if format_filter:
            query = query.where(GeoFile.file_format == format_filter)
        count_result = await self._db.execute(select(func.count()).select_from(query.subquery()))
        total = count_result.scalar_one()
        query = query.order_by(GeoFile.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self._db.execute(query)
        return (list(result.scalars().all()), total)

    async def update_status(self, file_id: str, status: ProcessingStatus, error_message: str | None=None, job_id: str | None=None) -> None:
        values: dict[str, Any] = {'status': status}
        if error_message is not None:
            values['error_message'] = error_message
        if job_id is not None:
            values['job_id'] = job_id
        await self._db.execute(update(GeoFile).where(GeoFile.id == file_id).values(**values))

    async def update_measurement_result(self, file_id: str, result: dict[str, Any], geometry_wkb: str | None=None) -> None:
        values: dict[str, Any] = {'measurement_result': result, 'status': ProcessingStatus.COMPLETED}
        if geometry_wkb:
            values['geometry'] = geometry_wkb
        await self._db.execute(update(GeoFile).where(GeoFile.id == file_id).values(**values))

    async def save_features(self, features: list[GeoFeature]) -> None:
        self._db.add_all(features)
        await self._db.flush()

    async def delete(self, file_id: str, owner_id: str) -> bool:
        geo_file = await self.get_by_id_with_owner_check(file_id, owner_id)
        if not geo_file:
            return False
        await self._db.delete(geo_file)
        return True
