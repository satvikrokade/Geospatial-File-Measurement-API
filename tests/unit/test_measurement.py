from __future__ import annotations
import math
import pytest
import geopandas as gpd
from pyproj import CRS, Transformer
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.ops import transform
from app.services.measurement_service import MeasurementService, _geodesic_area_perimeter, _geodesic_length, _wgs84_centroid
from app.core.exceptions import UnsupportedCRSError

@pytest.fixture
def service() -> MeasurementService:
    return MeasurementService()

def _make_utm_square_wgs84(center_lon: float, center_lat: float, side_m: float) -> Polygon:
    from pyproj import CRS, Transformer
    from shapely.geometry import box
    from shapely.ops import transform
    utm_crs = CRS.from_dict({'proj': 'utm', 'zone': int((center_lon + 180) / 6) + 1, 'ellps': 'WGS84'})
    wgs84 = CRS.from_epsg(4326)
    to_utm = Transformer.from_crs(wgs84, utm_crs, always_xy=True)
    to_wgs84 = Transformer.from_crs(utm_crs, wgs84, always_xy=True)
    cx, cy = to_utm.transform(center_lon, center_lat)
    half = side_m / 2
    sq_utm = box(cx - half, cy - half, cx + half, cy + half)
    sq_wgs84 = transform(to_wgs84.transform, sq_utm)
    return sq_wgs84

class TestGeodesicArea:

    def test_1km_square_is_approx_100_ha(self) -> None:
        sq = _make_utm_square_wgs84(center_lon=9.0, center_lat=48.0, side_m=1000.0)
        area_m2, _ = _geodesic_area_perimeter(sq)
        area_ha = area_m2 / 10000
        assert abs(area_ha - 100.0) < 0.5, f'Expected ≈ 100 ha, got {area_ha:.4f} ha'

    def test_area_is_never_in_degrees(self) -> None:
        poly = Polygon([(-0.5, 51.0), (0.5, 51.0), (0.5, 51.5), (-0.5, 51.5), (-0.5, 51.0)])
        area_m2, _ = _geodesic_area_perimeter(poly)
        assert area_m2 > 100000000.0, f'Area {area_m2} is suspiciously small — might be in degrees'

    def test_multipolygon_area_is_sum_of_parts(self) -> None:
        p1 = Polygon([(0, 0), (0.01, 0), (0.01, 0.01), (0, 0.01), (0, 0)])
        p2 = Polygon([(0.02, 0), (0.03, 0), (0.03, 0.01), (0.02, 0.01), (0.02, 0)])
        mp = MultiPolygon([p1, p2])
        area_mp, _ = _geodesic_area_perimeter(mp)
        area_p1, _ = _geodesic_area_perimeter(p1)
        area_p2, _ = _geodesic_area_perimeter(p2)
        assert abs(area_mp - (area_p1 + area_p2)) < 0.1, 'MultiPolygon area should equal sum of parts'

    def test_polygon_with_hole_area_less_than_exterior(self) -> None:
        exterior = Polygon([(0, 0), (0.1, 0), (0.1, 0.1), (0, 0.1), (0, 0)])
        hole = Polygon([(0.02, 0.02), (0.08, 0.02), (0.08, 0.08), (0.02, 0.08), (0.02, 0.02)])
        poly_with_hole = Polygon(exterior.exterior.coords, [hole.exterior.coords])
        area_full, _ = _geodesic_area_perimeter(exterior)
        area_holed, _ = _geodesic_area_perimeter(poly_with_hole)
        assert area_holed < area_full, 'Polygon with hole must have less area'

    def test_london_box_reference_area(self) -> None:
        poly = Polygon([(-0.5, 51.0), (0.5, 51.0), (0.5, 51.5), (-0.5, 51.5), (-0.5, 51.0)])
        area_m2, _ = _geodesic_area_perimeter(poly)
        area_km2 = area_m2 / 1000000.0
        assert 3880 < area_km2 < 3940, f'London box area {area_km2:.2f} km² outside expected range [3880, 3940]'

    def test_linestring_length_geodesic(self) -> None:
        line = LineString([(0, 0), (1, 0)])
        length_m = _geodesic_length(line)
        assert 111000 < length_m < 111700, f'Expected ≈ 111.32 km, got {length_m / 1000:.2f} km'

    def test_centroid_computed_in_projected_space(self) -> None:
        poly = Polygon([(-0.5, 51.0), (0.5, 51.0), (0.5, 51.5), (-0.5, 51.5), (-0.5, 51.0)])
        crs = CRS.from_epsg(4326)
        centroid = _wgs84_centroid(poly, crs)
        assert -0.5 <= centroid.longitude <= 0.5
        assert 51.0 <= centroid.latitude <= 51.5

class TestMeasurementService:

    def test_geojson_polygon_measurement(self, service: MeasurementService, simple_geojson_file) -> None:
        gdf = gpd.read_file(str(simple_geojson_file))
        gdf = gdf.set_crs('EPSG:4326', allow_override=True)
        result, features = service.measure(gdf=gdf, source_crs_str='EPSG:4326', file_id='test-001', filename='simple.geojson', file_format='geojson')
        assert result.feature_count == 1
        assert result.calculation_method == 'geodesic_wgs84'
        assert result.total_area_m2 is not None
        assert result.total_area_m2 > 0
        assert result.centroid_wgs84 is not None
        assert result.bounding_box is not None
        assert len(features) == 1

    def test_point_geometry_no_area(self, service: MeasurementService) -> None:
        gdf = gpd.GeoDataFrame({'geometry': [Point(10.0, 20.0)]}, crs='EPSG:4326')
        result, features = service.measure(gdf=gdf, source_crs_str='EPSG:4326', file_id='test-002', filename='point.geojson', file_format='geojson')
        assert result.total_area_m2 is None
        assert features[0].point_count == 1
        assert features[0].area_m2 is None

    def test_linestring_has_length_not_area(self, service: MeasurementService) -> None:
        gdf = gpd.GeoDataFrame({'geometry': [LineString([(0, 0), (1, 0)])]}, crs='EPSG:4326')
        result, features = service.measure(gdf=gdf, source_crs_str='EPSG:4326', file_id='test-003', filename='line.geojson', file_format='geojson')
        assert result.total_length_m is not None
        assert result.total_area_m2 is None
        assert features[0].length_m is not None

    def test_invalid_geometry_repaired(self, service: MeasurementService) -> None:
        bowtie = Polygon([(0, 0), (1, 1), (1, 0), (0, 1), (0, 0)])
        gdf = gpd.GeoDataFrame({'geometry': [bowtie]}, crs='EPSG:4326')
        result, features = service.measure(gdf=gdf, source_crs_str='EPSG:4326', file_id='test-004', filename='invalid.geojson', file_format='geojson')
        assert len(result.warnings) > 0 or len(features[0].warnings) > 0

    def test_unsupported_crs_raises(self, service: MeasurementService) -> None:
        gdf = gpd.GeoDataFrame({'geometry': [Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])]}, crs='EPSG:4326')
        with pytest.raises(UnsupportedCRSError):
            service.measure(gdf=gdf, source_crs_str='EPSG:INVALID999999', file_id='test-005', filename='bad.geojson', file_format='geojson')

    def test_area_statistics(self, service: MeasurementService) -> None:
        polys = [Polygon([(i * 0.1, 0), (i * 0.1 + 0.05, 0), (i * 0.1 + 0.05, 0.05), (i * 0.1, 0.05), (i * 0.1, 0)]) for i in range(5)]
        gdf = gpd.GeoDataFrame({'geometry': polys}, crs='EPSG:4326')
        result, _ = service.measure(gdf=gdf, source_crs_str='EPSG:4326', file_id='test-006', filename='multi.geojson', file_format='geojson')
        assert result.area_statistics is not None
        assert result.area_statistics.total_m2 > 0
        assert result.area_statistics.min_m2 <= result.area_statistics.max_m2
        assert result.area_statistics.min_m2 <= result.area_statistics.median_m2
