"""
Script to generate shapefile ZIP fixture for tests.
Run: python scripts/create_shapefile_fixture.py
"""

import io
import pathlib
import struct
import zipfile

FIXTURE_DIR = pathlib.Path(__file__).parent.parent / "tests/fixtures/shapefiles"
FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

# WGS84 PRJ content
WGS84_PRJ = (
    'GEOGCS["GCS_WGS_1984",'
    'DATUM["D_WGS_1984",'
    'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],'
    'UNIT["Degree",0.0174532925199433]]'
)

# Simple shapefile for a London polygon: -0.5,51.0 to 0.5,51.5
# Hand-crafting a minimal SHP/SHX/DBF for testing

def _pack_int(v: int) -> bytes:
    return struct.pack(">i", v)

def _pack_int_le(v: int) -> bytes:
    return struct.pack("<i", v)

def _pack_double(v: float) -> bytes:
    return struct.pack("<d", v)

def create_minimal_shapefile_zip(output_path: pathlib.Path) -> None:
    """Create a minimal valid shapefile ZIP with one polygon."""

    # Polygon coordinates: London box
    lon_min, lat_min = -0.5, 51.0
    lon_max, lat_max =  0.5, 51.5
    coords = [
        (lon_min, lat_min),
        (lon_max, lat_min),
        (lon_max, lat_max),
        (lon_min, lat_max),
        (lon_min, lat_min),
    ]
    num_points = len(coords)

    # ── .shp ───────────────────────────────────────────────────────────────
    # Shape type 5 = Polygon
    SHAPE_TYPE = 5

    # Content record for one polygon
    content_length_words = (
        2 +        # shape type (4 bytes)
        8 * 4 +    # bounding box (32 bytes)
        2 +        # num parts (4 bytes)
        2 +        # num points (4 bytes)
        2 +        # parts array (4 bytes)
        num_points * 4  # points (8 bytes each × 2 coords = 16 each = num_points×8 bytes total... wait)
    )
    # Actual: shape_type(4) + bbox(32) + num_parts(4) + num_points(4) + parts(4*num_parts) + points(16*num_points)
    record_content_bytes = (
        4 +        # shape type
        32 +       # bounding box
        4 +        # num parts
        4 +        # num points
        4 +        # parts[0] = 0
        num_points * 16  # each point is 2 doubles = 16 bytes
    )
    content_length_words_actual = record_content_bytes // 2

    # File header
    file_length_bytes = 100 + 8 + record_content_bytes
    file_length_words = file_length_bytes // 2

    shp = io.BytesIO()
    # File header (100 bytes, big-endian magic)
    shp.write(struct.pack(">i", 9994))       # file code
    shp.write(b"\x00" * 20)                  # unused
    shp.write(struct.pack(">i", file_length_words))   # file length
    shp.write(struct.pack("<i", 1000))        # version
    shp.write(struct.pack("<i", SHAPE_TYPE))  # shape type
    # Bounding box
    for v in [lon_min, lat_min, lon_max, lat_max, 0.0, 0.0, 0.0, 0.0]:
        shp.write(struct.pack("<d", v))

    # Record header (8 bytes, big-endian)
    shp.write(struct.pack(">i", 1))           # record number (1-based)
    shp.write(struct.pack(">i", content_length_words_actual))

    # Record content
    shp.write(struct.pack("<i", SHAPE_TYPE))  # shape type
    # Bounding box
    for v in [lon_min, lat_min, lon_max, lat_max]:
        shp.write(struct.pack("<d", v))
    shp.write(struct.pack("<i", 1))           # num parts
    shp.write(struct.pack("<i", num_points))  # num points
    shp.write(struct.pack("<i", 0))           # parts[0] = 0
    # Points
    for lon, lat in coords:
        shp.write(struct.pack("<d", lon))
        shp.write(struct.pack("<d", lat))

    shp_bytes = shp.getvalue()

    # ── .shx ───────────────────────────────────────────────────────────────
    shx_length_bytes = 100 + 8  # header + one record
    shx_length_words = shx_length_bytes // 2

    shx = io.BytesIO()
    # File header
    shx.write(struct.pack(">i", 9994))
    shx.write(b"\x00" * 20)
    shx.write(struct.pack(">i", shx_length_words))
    shx.write(struct.pack("<i", 1000))
    shx.write(struct.pack("<i", SHAPE_TYPE))
    for v in [lon_min, lat_min, lon_max, lat_max, 0.0, 0.0, 0.0, 0.0]:
        shx.write(struct.pack("<d", v))

    # Index record
    offset_words = 50  # 100 bytes / 2
    shx.write(struct.pack(">i", offset_words))
    shx.write(struct.pack(">i", content_length_words_actual))

    shx_bytes = shx.getvalue()

    # ── .dbf ───────────────────────────────────────────────────────────────
    # Minimal DBF: version 3, one field "NAME" (char, 50)
    dbf = io.BytesIO()
    dbf.write(struct.pack("<B", 3))           # version
    dbf.write(struct.pack("<3B", 21, 1, 1))   # date (2021-01-01)
    dbf.write(struct.pack("<I", 1))           # num records
    header_size = 32 + 32 + 1                 # header + one field descriptor + terminator
    dbf.write(struct.pack("<H", header_size)) # header size
    dbf.write(struct.pack("<H", 51))          # record size (1 deletion flag + 50 bytes)
    dbf.write(b"\x00" * 20)                  # reserved

    # Field descriptor for "NAME"
    field_name = b"NAME\x00\x00\x00\x00\x00\x00\x00"
    dbf.write(field_name)                     # 11 bytes
    dbf.write(b"C")                           # field type char
    dbf.write(b"\x00" * 4)                    # reserved
    dbf.write(struct.pack("<B", 50))          # field length
    dbf.write(struct.pack("<B", 0))           # decimal count
    dbf.write(b"\x00" * 14)                   # reserved

    dbf.write(b"\r")                          # header terminator

    # One record
    dbf.write(b" ")                           # deletion flag
    dbf.write(b"London Box" + b" " * 40)      # NAME (50 bytes)

    dbf.write(b"\x1a")                        # EOF
    dbf_bytes = dbf.getvalue()

    # ── ZIP it ─────────────────────────────────────────────────────────────
    with zipfile.ZipFile(str(output_path), "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("test_london.shp", shp_bytes)
        zf.writestr("test_london.shx", shx_bytes)
        zf.writestr("test_london.dbf", dbf_bytes)
        zf.writestr("test_london.prj", WGS84_PRJ)

    print(f"Created: {output_path}")


if __name__ == "__main__":
    create_minimal_shapefile_zip(FIXTURE_DIR / "test_london.zip")
    print("Shapefile fixtures created.")
