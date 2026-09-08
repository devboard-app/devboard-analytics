import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import (
    close_mongo_connection,
    connect_to_mongo,
    ensure_indexes,
    get_database,
)
from app.exceptions_handlers import register_exception_handlers
from app.http_client import close_http_client, open_http_client
from app.routers.events import router as events_router
from app.routers.reports import router as reports_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo() 
    await ensure_indexes()
    await open_http_client()
    yield
    await close_http_client()
    await close_mongo_connection()

app = FastAPI(
    title="Devboard Analytics Service",
    lifespan = lifespan
)
register_exception_handlers(app)
app.include_router(events_router)
app.include_router(reports_router)

@app.get("/health")
async def health():
    return{"status": "ok"}


@app.get("/health/db")
async def health_db(db: AsyncIOMotorDatabase = Depends(get_database)):  # noqa: B008
    try:
        await db.command("ping")
        return JSONResponse(status_code=200, content={"status": "ok"})
    except Exception:  # noqa: BLE001
        return JSONResponse(status_code=500, content={"status": "error", "details": "db unavailable"})