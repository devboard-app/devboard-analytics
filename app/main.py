from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import close_mongo_connection, connect_to_mongo, get_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo() 
    yield
    await close_mongo_connection()   


app = FastAPI(
    title="Devboard Analytics Service",
    lifespan = lifespan
)

@app.get("/health")
async def health():
    return{"status": "ok"}


@app.get("/health/db")
async def health_db(db: AsyncIOMotorDatabase = Depends(get_database)):
    try:
        await db.command("ping")
        return JSONResponse(status_code=200, content={"status": "ok"})
    except Exception:
        return JSONResponse(status_code=500, content={"status": "error", "details": "db unavailable"})