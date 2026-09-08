from fastapi import FastAPI
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
        return JSONResponse(status_code=404, content={"detail":"Sprint not found"})

    @app.exception_handler(SprintWindowMissingException)
    async def sprint_window_missing_handler(request, exc):
        return JSONResponse(status_code=409, content={"detail": "Sprint has no start or end date, burndown cannot be computed."})

    @app.exception_handler(ForbiddenException)
    async def forbidden_handler(request, exc):
        return JSONResponse(status_code=403, content={"detail": "Forbidden"})

    @app.exception_handler(UnauthorizedException)
    async def unauthorized_handler(request, exc):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    @app.exception_handler(ServiceUnavailableException)
    async def service_unavailable_handler(request, exc):
        return JSONResponse(status_code=503, content={"detail": f"{exc} unavailable."})