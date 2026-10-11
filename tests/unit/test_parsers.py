from __future__ import annotations
import io
import pathlib
import struct
import zipfile
import pytest
from app.core.exceptions import InvalidFileError, MissingCRSError, ZipSecurityError
from app.services.parsers import GeoJSONParser, KMLParser, ShapefileParser, build_parser_factory

@pytest.fixture
def geojson_parser() -> GeoJSONParser:
    return GeoJSONParser()

@pytest.fixture
def kml_parser() -> KMLParser:
    return KMLParser()

@pytest.fixture
def shapefile_parser() -> ShapefileParser:
    return ShapefileParser()

class TestGeoJSONParser:

    def test_parse_valid_file(self, geojson_parser: GeoJSONParser, geojson_file: pathlib.Path) -> None:
        gdf, crs = geojson_parser.parse(geojson_file)
        assert not gdf.empty
        assert crs == 'EPSG:4326'
        assert len(gdf) >= 1

    def test_parse_simple_geojson(self, geojson_parser: GeoJSONParser, simple_geojson_file: pathlib.Path) -> None:
        gdf, crs = geojson_parser.parse(simple_geojson_file)
        assert crs == 'EPSG:4326'
        assert len(gdf) == 1

    def test_parse_invalid_raises(self, geojson_parser: GeoJSONParser, tmp_path: pathlib.Path) -> None:
        bad = tmp_path / 'bad.geojson'
        bad.write_text('this is not json')
        with pytest.raises(InvalidFileError):
            geojson_parser.parse(bad)

    def test_parse_empty_raises(self, geojson_parser: GeoJSONParser, tmp_path: pathlib.Path) -> None:
        empty = tmp_path / 'empty.geojson'
        empty.write_text('{"type":"FeatureCollection","features":[]}')
        with pytest.raises(InvalidFileError, match='no features'):
            geojson_parser.parse(empty)

class TestKMLParser:

    def test_parse_valid_kml(self, kml_parser: KMLParser, kml_file: pathlib.Path) -> None:
        gdf, crs = kml_parser.parse(kml_file)
        assert not gdf.empty
        assert crs == 'EPSG:4326'

    def test_parse_invalid_kml_raises(self, kml_parser: KMLParser, tmp_path: pathlib.Path) -> None:
        bad = tmp_path / 'bad.kml'
        bad.write_text('not xml at all !!!')
        with pytest.raises(InvalidFileError):
            kml_parser.parse(bad)

class TestShapefileParser:

    def test_parse_valid_zip(self, shapefile_parser: ShapefileParser, shapefile_zip: pathlib.Path) -> None:
        gdf, crs = shapefile_parser.parse(shapefile_zip)
        assert not gdf.empty
        assert 'EPSG:' in crs or 'WGS' in crs.upper()

    def test_missing_shp_raises(self, shapefile_parser: ShapefileParser, tmp_path: pathlib.Path) -> None:
        zip_path = tmp_path / 'no_shp.zip'
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr('test.dbf', b'dummy')
            zf.writestr('test.shx', b'dummy')
        with pytest.raises(InvalidFileError, match='missing'):
            shapefile_parser.parse(zip_path)

    def test_missing_prj_raises_missing_crs_error(self, shapefile_parser: ShapefileParser, tmp_path: pathlib.Path) -> None:
        zip_path = tmp_path / 'no_prj.zip'
        src = pathlib.Path('tests/fixtures/shapefiles/test_london.zip')
        if src.exists():
            with zipfile.ZipFile(str(src)) as src_zf:
                with zipfile.ZipFile(str(zip_path), 'w') as dst_zf:
                    for name in src_zf.namelist():
                        if not name.endswith('.prj'):
                            dst_zf.writestr(name, src_zf.read(name))
        else:
            with zipfile.ZipFile(str(zip_path), 'w') as zf:
                zf.writestr('test.shp', b'PK' + b'\x00' * 100)
                zf.writestr('test.shx', b'PK' + b'\x00' * 100)
                zf.writestr('test.dbf', b'\x03\x15\x01\x01' + b'\x00' * 28)
        with pytest.raises(MissingCRSError):
            shapefile_parser.parse(zip_path)

    def test_zip_slip_attempt_rejected(self, shapefile_parser: ShapefileParser, tmp_path: pathlib.Path) -> None:
        zip_path = tmp_path / 'zipslip.zip'
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr('../../../etc/passwd', 'malicious content')
            zf.writestr('test.shp', b'dummy')
            zf.writestr('test.shx', b'dummy')
            zf.writestr('test.dbf', b'dummy')
            zf.writestr('test.prj', 'dummy wkt')
        with pytest.raises(ZipSecurityError, match='Zip-slip'):
            shapefile_parser.parse(zip_path)

    def test_not_a_zip_raises(self, shapefile_parser: ShapefileParser, tmp_path: pathlib.Path) -> None:
        not_zip = tmp_path / 'fake.zip'
        not_zip.write_bytes(b'definitely not a zip file')
        with pytest.raises(InvalidFileError, match='ZIP'):
            shapefile_parser.parse(not_zip)

class TestParserFactory:

    def test_geojson_extensions(self) -> None:
        factory = build_parser_factory()
        parser = factory.get_parser('.geojson')
        assert isinstance(parser, GeoJSONParser)
        parser2 = factory.get_parser('.json')
        assert isinstance(parser2, GeoJSONParser)

    def test_kml_extension(self) -> None:
        factory = build_parser_factory()
        parser = factory.get_parser('.kml')
        assert isinstance(parser, KMLParser)

    def test_zip_extension(self) -> None:
        factory = build_parser_factory()
        parser = factory.get_parser('.zip')
        assert isinstance(parser, ShapefileParser)

    def test_unsupported_extension_raises(self) -> None:
        from app.core.exceptions import UnsupportedFormatError
        factory = build_parser_factory()
        with pytest.raises(UnsupportedFormatError):
            factory.get_parser('.gpx')
