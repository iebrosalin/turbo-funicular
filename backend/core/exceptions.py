from fastapi import Request, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
import logging
import traceback
import json

logger = logging.getLogger(__name__)


class AppException(Exception):
    """Базовое исключение для кастомных ошибок приложения."""
    
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


async def global_exception_handler(request: Request, exc: AppException):
    """Обработчик кастомных исключений приложения."""
    logger.error("=" * 80)
    logger.error(f"🚨 AppException | Status: {exc.status_code}")
    logger.error(f"   URL: {request.method} {request.url}")
    logger.error(f"   Client: {request.client.host if request.client else 'unknown'}")
    logger.error(f"   Message: {exc.message}")
    logger.error("=" * 80)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Обработчик ошибок валидации."""
    logger.error("=" * 80)
    logger.error(f"🚨 Validation Error | Status: 422")
    logger.error(f"   URL: {request.method} {request.url}")
    logger.error(f"   Client: {request.client.host if request.client else 'unknown'}")
    logger.error(f"   Errors: {json.dumps(exc.errors(), indent=2, default=str)}")
    
    # Преобразуем ошибки в сериализуемый формат
    errors_serializable = []
    for error in exc.errors():
        errors_serializable.append({
            "loc": error.get("loc", []),
            "msg": error.get("msg", ""),
            "type": error.get("type", "")
        })
    
    # Обрабатываем body - преобразуем bytes в строку если необходимо
    body_value = exc.body
    if isinstance(body_value, bytes):
        body_value = body_value.decode('utf-8', errors='ignore')
    
    logger.error(f"   Request Body: {body_value[:1000] if body_value else 'empty'}")
    logger.error("=" * 80)
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": errors_serializable, "body": str(body_value)},
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Обработчик ошибок базы данных."""
    logger.error("=" * 80)
    logger.error(f"🚨 SQLAlchemy Error | Status: 500")
    logger.error(f"   URL: {request.method} {request.url}")
    logger.error(f"   Client: {request.client.host if request.client else 'unknown'}")
    logger.error(f"   Error: {str(exc)}")
    logger.error(f"   Type: {type(exc).__name__}")
    logger.error(f"   Traceback:\n{traceback.format_exc()}")
    logger.error("=" * 80)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Внутренняя ошибка сервера (База данных)"},
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """Обработчик HTTP исключений (включая 500)."""
    logger.error("=" * 80)
    logger.error(f"🚨 HTTPException | Status: {exc.status_code}")
    logger.error(f"   URL: {request.method} {request.url}")
    logger.error(f"   Client: {request.client.host if request.client else 'unknown'}")
    logger.error(f"   Detail: {exc.detail}")
    logger.error("=" * 80)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


async def generic_exception_handler(request: Request, exc: Exception):
    """Обработчик общих исключений."""
    logger.error("=" * 80)
    logger.error(f"🚨 Unhandled Exception | Status: 500")
    logger.error(f"   URL: {request.method} {request.url}")
    logger.error(f"   Client: {request.client.host if request.client else 'unknown'}")
    logger.error(f"   Exception Type: {type(exc).__name__}")
    logger.error(f"   Message: {str(exc)}")
    logger.error(f"   Full Traceback:\n{traceback.format_exc()}")
    logger.error("=" * 80)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Внутренняя ошибка сервера"},
    )
