"""Global exception handlers — retornam sempre JSON estruturado."""

from fastapi import Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    logger.warning(
        "HTTP {status} | {method} {path} | {detail}",
        status=exc.status_code,
        method=request.method,
        path=request.url.path,
        detail=exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "http_error",
            "detail": str(exc.detail),
            "code": exc.status_code,
        },
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.warning(
        "Validation error | {method} {path} | {errors}",
        method=request.method,
        path=request.url.path,
        errors=exc.errors(),
    )
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "detail": exc.errors(),
            "code": 422,
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.opt(exception=True).error(
        "Unhandled exception | {method} {path}",
        method=request.method,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "detail": "Erro interno do servidor. Consulte os logs para detalhes.",
            "code": 500,
        },
    )


def register_exception_handlers(app):
    """Registra todos os handlers de exceção na aplicação FastAPI."""
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)