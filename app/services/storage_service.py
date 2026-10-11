from __future__ import annotations
import shutil
import uuid
from pathlib import Path
import magic
from app.core.config import get_settings
from app.core.exceptions import FileSizeLimitError, InvalidFileError, UnsupportedFormatError
from app.core.logging import get_logger
_logger = get_logger(__name__)
_ALLOWED_EXTENSIONS = {'.geojson': {'application/json', 'application/geo+json', 'text/plain'}, '.json': {'application/json', 'text/plain'}, '.kml': {'application/vnd.google-earth.kml+xml', 'text/xml', 'text/plain', 'application/xml'}, '.zip': {'application/zip', 'application/x-zip-compressed', 'application/octet-stream'}}
_ZIP_MAGIC = b'PK\x03\x04'
_JSON_MAGIC_CHARS = frozenset(b' \t\n\r\xef\xbb\xbf{[')

class StorageService:

    def __init__(self) -> None:
        self._settings = get_settings()
        self._upload_dir = self._settings.upload_dir
        self._upload_dir.mkdir(parents=True, exist_ok=True)

    def validate_and_store(self, file_content: bytes, original_filename: str) -> tuple[str, Path, str]:
        size = len(file_content)
        if size > self._settings.max_file_size_bytes:
            raise FileSizeLimitError(f'File size {size / 1024 ** 2:.1f} MB exceeds limit of {self._settings.max_file_size_mb} MB')
        if size == 0:
            raise InvalidFileError('Uploaded file is empty')
        suffix = Path(original_filename).suffix.lower()
        if suffix not in _ALLOWED_EXTENSIONS:
            raise UnsupportedFormatError(f"File extension '{suffix}' is not supported", details={'supported': list(_ALLOWED_EXTENSIONS.keys())})
        try:
            detected_mime = magic.from_buffer(file_content[:2048], mime=True)
        except Exception:
            detected_mime = 'application/octet-stream'
        allowed_mimes = _ALLOWED_EXTENSIONS[suffix]
        if detected_mime not in allowed_mimes and (not self._is_text_geojson(file_content, suffix)):
            _logger.warning('mime_mismatch', extension=suffix, detected_mime=detected_mime, allowed=sorted(allowed_mimes))
        self._check_magic_bytes(file_content, suffix, original_filename)
        stored_name = f'{uuid.uuid4()}{suffix}'
        stored_path = self._upload_dir / stored_name
        stored_path.write_bytes(file_content)
        _logger.info('file_stored', original=original_filename, stored=stored_name, size_bytes=size)
        return (stored_name, stored_path, suffix)

    def delete_file(self, stored_filename: str) -> bool:
        path = self._upload_dir / stored_filename
        if path.exists():
            path.unlink()
            return True
        return False

    def get_path(self, stored_filename: str) -> Path:
        return self._upload_dir / stored_filename

    def _check_magic_bytes(self, content: bytes, suffix: str, filename: str) -> None:
        if suffix == '.zip':
            if not content[:4] == _ZIP_MAGIC:
                raise InvalidFileError('File does not have a valid ZIP signature (PK header missing)', details={'filename': filename})
        elif suffix in ('.geojson', '.json'):
            stripped = content[:100].lstrip(b' \t\n\r\xef\xbb\xbf')
            if not stripped or stripped[0:1] not in (b'{', b'['):
                raise InvalidFileError('File does not appear to be valid JSON/GeoJSON', details={'filename': filename})
        elif suffix == '.kml':
            stripped = content[:200].lstrip(b' \t\n\r')
            if not (stripped.startswith(b'<?xml') or stripped.startswith(b'<kml') or b'<kml' in stripped[:500]):
                raise InvalidFileError('File does not appear to be valid KML (no KML/XML header found)', details={'filename': filename})

    @staticmethod
    def _is_text_geojson(content: bytes, suffix: str) -> bool:
        return suffix in ('.geojson', '.json')
