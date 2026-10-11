from __future__ import annotations
import enum
from typing import Any
from geoalchemy2 import Geography
from sqlalchemy import BigInteger, Enum, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin, new_uuid

class FileFormat(str, enum.Enum):
    GEOJSON = 'geojson'
    KML = 'kml'
    SHAPEFILE = 'shapefile'

class ProcessingStatus(str, enum.Enum):
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'

class GeoFile(Base, TimestampMixin):
    __tablename__ = 'geo_files'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid, index=True)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    file_format: Mapped[FileFormat] = mapped_column(Enum(FileFormat, name='file_format_enum'), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ProcessingStatus] = mapped_column(Enum(ProcessingStatus, name='processing_status_enum'), default=ProcessingStatus.PENDING, nullable=False, index=True)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_crs: Mapped[str | None] = mapped_column(String(64), nullable=True)
    measurement_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    geometry: Mapped[Any | None] = mapped_column(Geography(geometry_type='GEOMETRY', srid=4326, spatial_index=False), nullable=True)
    owner: Mapped['User'] = relationship('User', back_populates='geo_files')
    features: Mapped[list['GeoFeature']] = relationship('GeoFeature', back_populates='geo_file', cascade='all, delete-orphan')
    __table_args__ = (Index('ix_geo_files_owner_created', 'owner_id', 'created_at'), Index('ix_geo_files_geom_gist', 'geometry', postgresql_using='gist'))

    def __repr__(self) -> str:
        return f'<GeoFile id={self.id!r} format={self.file_format!r} status={self.status!r}>'

class GeoFeature(Base, TimestampMixin):
    __tablename__ = 'geo_features'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid, index=True)
    geo_file_id: Mapped[str] = mapped_column(String(36), ForeignKey('geo_files.id', ondelete='CASCADE'), nullable=False, index=True)
    feature_index: Mapped[int] = mapped_column(Integer, nullable=False)
    geometry_type: Mapped[str] = mapped_column(String(64), nullable=False)
    properties: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    measurements: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    warnings: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    geometry: Mapped[Any] = mapped_column(Geography(geometry_type='GEOMETRY', srid=4326, spatial_index=False), nullable=False)
    geo_file: Mapped['GeoFile'] = relationship('GeoFile', back_populates='features')
    __table_args__ = (Index('ix_geo_features_geom_gist', 'geometry', postgresql_using='gist'), Index('ix_geo_features_file_idx', 'geo_file_id', 'feature_index'))

    def __repr__(self) -> str:
        return f'<GeoFeature id={self.id!r} file={self.geo_file_id!r} idx={self.feature_index}>'
