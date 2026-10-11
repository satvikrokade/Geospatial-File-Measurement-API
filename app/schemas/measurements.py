from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field
AreaUnit = Literal['m2', 'km2', 'ha', 'acre']
LengthUnit = Literal['m', 'km', 'mi', 'ft']

class CoordinateSchema(BaseModel):
    longitude: float
    latitude: float

class BoundingBoxSchema(BaseModel):
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    @property
    def as_list(self) -> list[float]:
        return [self.min_lon, self.min_lat, self.max_lon, self.max_lat]

class FeatureMeasurementSchema(BaseModel):
    feature_index: int
    geometry_type: str
    area_m2: float | None = None
    perimeter_m: float | None = None
    length_m: float | None = None
    point_count: int | None = None
    centroid_wgs84: CoordinateSchema | None = None
    centroid_source_crs: CoordinateSchema | None = None
    bounding_box: BoundingBoxSchema | None = None
    properties: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)

class AreaStatisticsSchema(BaseModel):
    total_m2: float
    mean_m2: float
    min_m2: float
    max_m2: float
    median_m2: float

class GeometryTypeBreakdown(BaseModel):
    geometry_type: str
    count: int

class MeasurementResultSchema(BaseModel):
    file_id: str
    filename: str
    format: str
    source_crs: str
    calculation_method: str = Field(description="e.g. 'geodesic_wgs84', 'projected_utm32n', 'projected_equal_area'")
    feature_count: int
    geometry_type_breakdown: list[GeometryTypeBreakdown]
    total_area_m2: float | None = None
    total_perimeter_m: float | None = None
    total_length_m: float | None = None
    bounding_box: BoundingBoxSchema | None = None
    centroid_wgs84: CoordinateSchema | None = None
    area_statistics: AreaStatisticsSchema | None = None
    area_converted: float | None = None
    area_unit: str | None = None
    perimeter_converted: float | None = None
    perimeter_unit: str | None = None
    warnings: list[str] = Field(default_factory=list)

class FileUploadResponse(BaseModel):
    file_id: str
    status: str
    job_id: str | None = None
    message: str

class FileListItemSchema(BaseModel):
    id: str
    original_filename: str
    file_format: str
    file_size_bytes: int
    status: str
    feature_count: int | None = None
    total_area_m2: float | None = None
    created_at: str
    model_config = {'from_attributes': True}

class PaginatedFilesResponse(BaseModel):
    items: list[FileListItemSchema]
    total: int
    page: int
    page_size: int
    pages: int

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    file_id: str | None = None
    message: str | None = None
    progress: int | None = None
