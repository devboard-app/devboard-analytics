from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.exceptions import (
    ForbiddenException,
    ServiceUnavailableException,
    SprintNotFoundException,
    SprintWindowMissingException,
    UnauthorizedException,
)


def register_exception_handlers(app: FastAPI):
    @app.exception_handler(SprintNotFoundException)
    async def sprint_not_found_handler(request, exc):
        return JSONResponse(status_code=404, content={"detail": "Sprint not found", "errors": None})

    @app.exception_handler(SprintWindowMissingException)
    async def sprint_window_missing_handler(request, exc):
        return JSONResponse(status_code=409, content={"detail": "Sprint has no start or end date, burndown cannot be computed.", "errors": None})

    @app.exception_handler(ForbiddenException)
    async def forbidden_handler(request, exc):
        return JSONResponse(status_code=403, content={"detail": "Forbidden", "errors": None})

    @app.exception_handler(UnauthorizedException)
    async def unauthorized_handler(request, exc):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized", "errors": None})

    @app.exception_handler(ServiceUnavailableException)
    async def service_unavailable_handler(request, exc):
        return JSONResponse(status_code=503, content={"detail": f"{exc} unavailable.", "errors": None})

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request, exc):
        errors: dict[str, list[str]] = {}
        for error in exc.errors():
            field = str(error["loc"][-1]) if error["loc"] else "non_field_errors"
            errors.setdefault(field, []).append(error["msg"])
        if not errors:
            return JSONResponse(status_code=422, content={"detail": "Invalid request.", "errors": errors})
        return JSONResponse(status_code=422, content={"detail": next(iter(errors.values()))[0], "errors": errors})

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "errors": None})
    