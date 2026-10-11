from __future__ import annotations
import statistics
from collections import Counter
from typing import Any
import geopandas as gpd
import pyproj
from pyproj import CRS, Geod, Transformer
from shapely import make_valid
from shapely.geometry import GeometryCollection, LineString, MultiLineString, MultiPoint, MultiPolygon, Point, Polygon, mapping, shape
from shapely.ops import transform, unary_union
from shapely.validation import explain_validity
from app.core.exceptions import UnsupportedCRSError
from app.core.logging import get_logger
from app.schemas.measurements import AreaStatisticsSchema, BoundingBoxSchema, CoordinateSchema, FeatureMeasurementSchema, GeometryTypeBreakdown, MeasurementResultSchema
_logger = get_logger(__name__)
_WGS84_GEOD = Geod(ellps='WGS84')
_GEOGRAPHIC_AUTHORITY_CODES = frozenset(['EPSG:4326', 'EPSG:4269', 'EPSG:4258', 'CRS84', 'OGC:CRS84'])

def _is_geographic(crs: CRS) -> bool:
    return crs.is_geographic

def _utm_zone_from_centroid(lon: float, lat: float) -> CRS:
    zone_number = int((lon + 180) / 6) + 1
    hemisphere = 'north' if lat >= 0 else 'south'
    return CRS.from_dict({'proj': 'utm', 'zone': zone_number, 'south': lat < 0, 'ellps': 'WGS84'})

def _equal_area_crs() -> CRS:
    return CRS.from_epsg(54009)

def _reproject_geometry(geom: Any, from_crs: CRS, to_crs: CRS) -> Any:
    transformer = Transformer.from_crs(from_crs, to_crs, always_xy=True)
    return transform(transformer.transform, geom)

def _geodesic_area_perimeter(geom: Any) -> tuple[float, float]:
    area, perimeter = _WGS84_GEOD.geometry_area_perimeter(geom)
    return (abs(area), abs(perimeter))

def _geodesic_length(geom: Any) -> float:
    total = 0.0
    if geom.geom_type == 'LineString':
        coords = list(geom.coords)
        for i in range(len(coords) - 1):
            _, _, dist = _WGS84_GEOD.inv(coords[i][0], coords[i][1], coords[i + 1][0], coords[i + 1][1])
            total += dist
    elif geom.geom_type == 'MultiLineString':
        for line in geom.geoms:
            total += _geodesic_length(line)
    return total

def _projected_area_perimeter(geom: Any, source_crs: CRS) -> tuple[float, float]:
    return (geom.area, geom.length)

def _wgs84_centroid(geom: Any, source_crs: CRS) -> CoordinateSchema:
    wgs84 = CRS.from_epsg(4326)
    bbox = geom.bounds
    mid_lon = (bbox[0] + bbox[2]) / 2
    mid_lat = (bbox[1] + bbox[3]) / 2
    if _is_geographic(source_crs):
        utm_crs = _utm_zone_from_centroid(mid_lon, mid_lat)
        geom_utm = _reproject_geometry(geom, source_crs, utm_crs)
        centroid_utm = geom_utm.centroid
        centroid_wgs84 = _reproject_geometry(centroid_utm, utm_crs, wgs84)
    else:
        centroid_proj = geom.centroid
        centroid_wgs84 = _reproject_geometry(centroid_proj, source_crs, wgs84)
    return CoordinateSchema(longitude=round(centroid_wgs84.x, 8), latitude=round(centroid_wgs84.y, 8))

def _source_crs_centroid(geom: Any, source_crs: CRS) -> CoordinateSchema:
    if _is_geographic(source_crs):
        bbox = geom.bounds
        mid_lon = (bbox[0] + bbox[2]) / 2
        mid_lat = (bbox[1] + bbox[3]) / 2
        utm_crs = _utm_zone_from_centroid(mid_lon, mid_lat)
        geom_utm = _reproject_geometry(geom, source_crs, utm_crs)
        centroid_utm = geom_utm.centroid
        centroid_src = _reproject_geometry(centroid_utm, utm_crs, source_crs)
    else:
        centroid_src = geom.centroid
    return CoordinateSchema(longitude=round(centroid_src.x, 8), latitude=round(centroid_src.y, 8))

def _bounding_box(geom: Any, source_crs: CRS) -> BoundingBoxSchema:
    wgs84 = CRS.from_epsg(4326)
    if not _is_geographic(source_crs):
        geom = _reproject_geometry(geom, source_crs, wgs84)
    bounds = geom.bounds
    return BoundingBoxSchema(min_lon=round(bounds[0], 8), min_lat=round(bounds[1], 8), max_lon=round(bounds[2], 8), max_lat=round(bounds[3], 8))

def _validate_and_repair(geom: Any) -> tuple[Any, list[str]]:
    warnings: list[str] = []
    if not geom.is_valid:
        reason = explain_validity(geom)
        geom = make_valid(geom)
        warnings.append(f'Geometry repaired: {reason}')
        if not geom.is_valid:
            if hasattr(geom, 'geoms'):
                geom = unary_union(list(geom.geoms))
            warnings.append('Geometry partially repaired — results may be approximate')
    return (geom, warnings)

def _measure_single_feature(geom: Any, source_crs: CRS, feature_index: int, properties: dict[str, Any] | None, is_geographic: bool) -> FeatureMeasurementSchema:
    geom, warnings = _validate_and_repair(geom)
    area_m2: float | None = None
    perimeter_m: float | None = None
    length_m: float | None = None
    point_count: int | None = None
    centroid_wgs84: CoordinateSchema | None = None
    centroid_src: CoordinateSchema | None = None
    bbox: BoundingBoxSchema | None = None
    geom_type = geom.geom_type
    if geom_type in ('Polygon', 'MultiPolygon', 'GeometryCollection'):
        if is_geographic:
            area_m2, perimeter_m = _geodesic_area_perimeter(geom)
        else:
            area_m2, perimeter_m = _projected_area_perimeter(geom, source_crs)
        centroid_wgs84 = _wgs84_centroid(geom, source_crs)
        centroid_src = _source_crs_centroid(geom, source_crs)
        bbox = _bounding_box(geom, source_crs)
    elif geom_type in ('LineString', 'MultiLineString'):
        if is_geographic:
            length_m = _geodesic_length(geom)
        else:
            length_m = geom.length
        centroid_wgs84 = _wgs84_centroid(geom, source_crs)
        bbox = _bounding_box(geom, source_crs)
    elif geom_type in ('Point', 'MultiPoint'):
        point_count = 1 if geom_type == 'Point' else len(list(geom.geoms))
        centroid_wgs84 = _wgs84_centroid(geom, source_crs)
    return FeatureMeasurementSchema(feature_index=feature_index, geometry_type=geom_type, area_m2=round(area_m2, 4) if area_m2 is not None else None, perimeter_m=round(perimeter_m, 4) if perimeter_m is not None else None, length_m=round(length_m, 4) if length_m is not None else None, point_count=point_count, centroid_wgs84=centroid_wgs84, centroid_source_crs=centroid_src, bounding_box=bbox, properties=properties, warnings=warnings)

class MeasurementService:

    def measure(self, gdf: gpd.GeoDataFrame, source_crs_str: str, file_id: str, filename: str, file_format: str) -> tuple[MeasurementResultSchema, list[FeatureMeasurementSchema]]:
        try:
            source_crs = CRS.from_user_input(source_crs_str)
        except Exception as exc:
            raise UnsupportedCRSError(f"Cannot interpret CRS '{source_crs_str}': {exc}", details={'crs': source_crs_str}) from exc
        is_geographic = _is_geographic(source_crs)
        method = 'geodesic_wgs84' if is_geographic else f"projected_{source_crs_str.replace(':', '_').lower()}"
        _logger.info('starting_measurement', file_id=file_id, crs=source_crs_str, method=method, features=len(gdf))
        feature_results: list[FeatureMeasurementSchema] = []
        all_geoms: list[Any] = []
        global_warnings: list[str] = []
        if is_geographic:
            wgs84 = CRS.from_epsg(4326)
            if source_crs != wgs84:
                gdf = gdf.to_crs(wgs84)
                source_crs = wgs84
        for idx, row in gdf.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            properties = {k: v for k, v in row.items() if k != 'geometry' and v is not None}
            properties = {k: int(v) if hasattr(v, 'item') else v for k, v in properties.items()}
            fm = _measure_single_feature(geom=geom, source_crs=source_crs, feature_index=int(idx), properties=properties if properties else None, is_geographic=is_geographic)
            feature_results.append(fm)
            all_geoms.append(geom)
            global_warnings.extend(fm.warnings)
        areas = [f.area_m2 for f in feature_results if f.area_m2 is not None]
        perimeters = [f.perimeter_m for f in feature_results if f.perimeter_m is not None]
        lengths = [f.length_m for f in feature_results if f.length_m is not None]
        total_area = sum(areas) if areas else None
        total_perimeter = sum(perimeters) if perimeters else None
        total_length = sum(lengths) if lengths else None
        area_stats: AreaStatisticsSchema | None = None
        if len(areas) > 0:
            area_stats = AreaStatisticsSchema(total_m2=round(sum(areas), 4), mean_m2=round(statistics.mean(areas), 4), min_m2=round(min(areas), 4), max_m2=round(max(areas), 4), median_m2=round(statistics.median(areas), 4))
        overall_bbox: BoundingBoxSchema | None = None
        overall_centroid: CoordinateSchema | None = None
        if all_geoms:
            union_geom = unary_union(all_geoms)
            overall_bbox = _bounding_box(union_geom, source_crs)
            if any((f.geometry_type in ('Polygon', 'MultiPolygon', 'LineString', 'MultiLineString') for f in feature_results)):
                overall_centroid = _wgs84_centroid(union_geom, source_crs)
        type_counts = Counter((f.geometry_type for f in feature_results))
        breakdown = [GeometryTypeBreakdown(geometry_type=k, count=v) for k, v in sorted(type_counts.items())]
        result = MeasurementResultSchema(file_id=file_id, filename=filename, format=file_format, source_crs=source_crs_str, calculation_method=method, feature_count=len(feature_results), geometry_type_breakdown=breakdown, total_area_m2=round(total_area, 4) if total_area is not None else None, total_perimeter_m=round(total_perimeter, 4) if total_perimeter is not None else None, total_length_m=round(total_length, 4) if total_length is not None else None, bounding_box=overall_bbox, centroid_wgs84=overall_centroid, area_statistics=area_stats, warnings=list(dict.fromkeys(global_warnings)))
        _logger.info('measurement_completed', file_id=file_id, feature_count=result.feature_count, total_area_m2=result.total_area_m2, method=method)
        return (result, feature_results)
