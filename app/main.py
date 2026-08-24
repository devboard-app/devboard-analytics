from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import (
    close_mongo_connection,
    close_redis_connection,
    connect_to_mongo,
    connect_to_redis,
    get_database,
)
from app.routers.events import router as events_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo() 
    await connect_to_redis()
    yield
    await close_mongo_connection()
    await close_redis_connection()   


app = FastAPI(
    title="Devboard Analytics Service",
    lifespan = lifespan
)
app.include_router(events_router)

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