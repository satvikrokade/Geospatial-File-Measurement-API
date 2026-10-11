from __future__ import annotations
import io
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Protocol, runtime_checkable
import fiona
import geopandas as gpd
from pyproj import CRS
from app.core.exceptions import InvalidFileError, MissingCRSError, UnsupportedCRSError, ZipSecurityError
from app.core.logging import get_logger
_logger = get_logger(__name__)
_MAX_UNZIPPED_BYTES = 500 * 1024 * 1024
_MAX_ZIP_ENTRIES = 100

@runtime_checkable
class GeoFileParser(Protocol):

    def parse(self, file_path: Path) -> tuple[gpd.GeoDataFrame, str]:
        ...

class GeoJSONParser:

    def parse(self, file_path: Path) -> tuple[gpd.GeoDataFrame, str]:
        try:
            gdf = gpd.read_file(str(file_path))
        except Exception as exc:
            raise InvalidFileError(f'Cannot read GeoJSON file: {exc}', details={'filename': file_path.name}) from exc
        if gdf.empty:
            raise InvalidFileError('GeoJSON file contains no features')
        crs_str = 'EPSG:4326'
        if gdf.crs and gdf.crs != CRS.from_epsg(4326):
            _logger.warning('geojson_non_wgs84_crs_detected', crs=str(gdf.crs), file=file_path.name)
            crs_str = gdf.crs.to_epsg() and f'EPSG:{gdf.crs.to_epsg()}' or 'EPSG:4326'
        else:
            gdf = gdf.set_crs('EPSG:4326', allow_override=True)
        return (gdf, crs_str)

class KMLParser:

    def parse(self, file_path: Path) -> tuple[gpd.GeoDataFrame, str]:
        fiona.drvsupport.supported_drivers['KML'] = 'rw'
        fiona.drvsupport.supported_drivers['LIBKML'] = 'rw'
        try:
            layers = fiona.listlayers(str(file_path))
        except Exception as exc:
            raise InvalidFileError(f'Cannot read KML file: {exc}', details={'filename': file_path.name}) from exc
        if not layers:
            raise InvalidFileError('KML file has no readable layers')
        gdfs: list[gpd.GeoDataFrame] = []
        for layer in layers:
            try:
                gdf_layer = gpd.read_file(str(file_path), driver='KML', layer=layer)
                if not gdf_layer.empty:
                    gdfs.append(gdf_layer)
            except Exception as exc:
                _logger.warning('kml_layer_read_error', layer=layer, error=str(exc))
        if not gdfs:
            raise InvalidFileError('KML file contains no readable geometry layers')
        gdf = gpd.pd.concat(gdfs, ignore_index=True)
        gdf = gpd.GeoDataFrame(gdf, geometry='geometry')
        gdf = gdf.set_crs('EPSG:4326', allow_override=True)
        gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()]
        if gdf.empty:
            raise InvalidFileError('KML file contains no non-empty geometries')
        return (gdf, 'EPSG:4326')

def _check_zip_safety(zf: zipfile.ZipFile) -> None:
    entries = zf.infolist()
    if len(entries) > _MAX_ZIP_ENTRIES:
        raise ZipSecurityError(f'ZIP contains {len(entries)} entries (max {_MAX_ZIP_ENTRIES})')
    total_size = 0
    for entry in entries:
        total_size += entry.file_size
        if total_size > _MAX_UNZIPPED_BYTES:
            raise ZipSecurityError(f'ZIP uncompressed content exceeds {_MAX_UNZIPPED_BYTES // 1024 ** 2} MB')
        entry_path = Path(entry.filename)
        if entry_path.is_absolute() or '..' in entry_path.parts:
            raise ZipSecurityError(f'Zip-slip attempt detected in entry: {entry.filename}')

class ShapefileParser:
    REQUIRED_EXTENSIONS = frozenset(['.shp', '.dbf', '.shx'])
    ALLOWED_EXTENSIONS = frozenset(['.shp', '.dbf', '.shx', '.prj', '.cpg', '.qpj'])

    def parse(self, file_path: Path) -> tuple[gpd.GeoDataFrame, str]:
        if not zipfile.is_zipfile(str(file_path)):
            raise InvalidFileError('Shapefile upload must be a ZIP archive')
        with zipfile.ZipFile(str(file_path), 'r') as zf:
            _check_zip_safety(zf)
            names = [Path(n).name.lower() for n in zf.namelist() if not n.endswith('/')]
            extensions = {Path(n).suffix.lower() for n in names}
            missing = self.REQUIRED_EXTENSIONS - extensions
            if missing:
                raise InvalidFileError('ZIP is missing required Shapefile components', details={'missing': sorted(missing)})
            with tempfile.TemporaryDirectory() as tmpdir:
                for member in zf.infolist():
                    member_path = Path(member.filename)
                    if member_path.suffix.lower() in self.ALLOWED_EXTENSIONS and (not member.is_dir()):
                        target = Path(tmpdir) / member_path.name
                        with zf.open(member) as src, open(target, 'wb') as dst:
                            dst.write(src.read())
                shp_files = list(Path(tmpdir).glob('*.shp'))
                if not shp_files:
                    raise InvalidFileError('No .shp file found after extraction')
                shp_path = shp_files[0]
                prj_files = list(Path(tmpdir).glob('*.prj'))
                crs_str = self._resolve_crs(shp_path, prj_files)
                try:
                    gdf = gpd.read_file(str(shp_path))
                except Exception as exc:
                    raise InvalidFileError(f'Cannot read Shapefile: {exc}', details={'filename': file_path.name}) from exc
                if gdf.empty:
                    raise InvalidFileError('Shapefile contains no features')
                if gdf.crs is None and crs_str:
                    gdf = gdf.set_crs(crs_str)
                elif gdf.crs is not None:
                    crs_str = self._crs_to_str(gdf.crs)
                return (gdf, crs_str)

    def _resolve_crs(self, shp_path: Path, prj_files: list[Path]) -> str:
        if not prj_files:
            raise MissingCRSError('Shapefile ZIP is missing the .prj file. Cannot determine the coordinate reference system. Please include a valid .prj file.', details={'shapefile': shp_path.name})
        prj_path = prj_files[0]
        wkt = prj_path.read_text(encoding='utf-8', errors='replace').strip()
        if not wkt:
            raise MissingCRSError('.prj file exists but is empty', details={'prj': prj_path.name})
        try:
            crs = CRS.from_wkt(wkt)
        except Exception as exc:
            raise UnsupportedCRSError(f'Cannot parse .prj WKT: {exc}', details={'wkt_preview': wkt[:200]}) from exc
        return self._crs_to_str(crs)

    @staticmethod
    def _crs_to_str(crs: CRS) -> str:
        epsg = crs.to_epsg()
        if epsg:
            return f'EPSG:{epsg}'
        auth = crs.to_authority()
        if auth:
            return f'{auth[0]}:{auth[1]}'
        return crs.to_wkt()

class ParserFactory:

    def __init__(self) -> None:
        self._registry: dict[str, GeoFileParser] = {}

    def register(self, extension: str, parser: GeoFileParser) -> None:
        self._registry[extension.lower()] = parser

    def get_parser(self, extension: str) -> GeoFileParser:
        parser = self._registry.get(extension.lower())
        if not parser:
            from app.core.exceptions import UnsupportedFormatError
            raise UnsupportedFormatError(f"No parser registered for extension '{extension}'", details={'extension': extension, 'supported': list(self._registry.keys())})
        return parser

def build_parser_factory() -> ParserFactory:
    factory = ParserFactory()
    factory.register('.geojson', GeoJSONParser())
    factory.register('.json', GeoJSONParser())
    factory.register('.kml', KMLParser())
    factory.register('.zip', ShapefileParser())
    return factory
default_parser_factory = build_parser_factory()
