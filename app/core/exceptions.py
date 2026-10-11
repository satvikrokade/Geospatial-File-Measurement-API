from __future__ import annotations
from typing import Any
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

class GeoAPIException(Exception):
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = 'internal_error'

    def __init__(self, message: str, details: Any=None) -> None:
        self.message = message
        self.details = details
        super().__init__(message)

class InvalidFileError(GeoAPIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = 'invalid_file'

class UnsupportedFormatError(GeoAPIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = 'unsupported_format'

class CorruptGeometryError(GeoAPIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = 'corrupt_geometry'

class UnsupportedCRSError(GeoAPIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = 'unsupported_crs'

class MissingCRSError(GeoAPIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = 'missing_crs'

class ZipSecurityError(GeoAPIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = 'zip_security_violation'

class FileSizeLimitError(GeoAPIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    code = 'file_too_large'

class ResourceNotFoundError(GeoAPIException):
    status_code = status.HTTP_404_NOT_FOUND
    code = 'not_found'

class UnauthorizedError(GeoAPIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = 'unauthorized'

class ForbiddenError(GeoAPIException):
    status_code = status.HTTP_403_FORBIDDEN
    code = 'forbidden'

class JobNotFoundError(GeoAPIException):
    status_code = status.HTTP_404_NOT_FOUND
    code = 'job_not_found'

class ProcessingError(GeoAPIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = 'processing_error'

def _error_response(status_code: int, code: str, message: str, details: Any=None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={'error': {'code': code, 'message': message, 'details': details}})

async def geo_api_exception_handler(request: Request, exc: GeoAPIException) -> JSONResponse:
    return _error_response(exc.status_code, exc.code, exc.message, exc.details)

async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code_map = {401: 'unauthorized', 403: 'forbidden', 404: 'not_found', 405: 'method_not_allowed', 429: 'rate_limit_exceeded'}
    code = code_map.get(exc.status_code, 'http_error')
    return _error_response(exc.status_code, code, str(exc.detail))

async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [{'field': '.'.join((str(loc) for loc in err['loc'])), 'message': err['msg'], 'type': err['type']} for err in exc.errors()]
    return _error_response(status.HTTP_422_UNPROCESSABLE_ENTITY, 'validation_error', 'Request validation failed', details)

async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    from app.core.logging import get_logger
    logger = get_logger(__name__)
    logger.exception('Unhandled exception', path=str(request.url), exc_info=exc)
    return _error_response(500, 'internal_error', 'An unexpected error occurred')

def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(GeoAPIException, geo_api_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
