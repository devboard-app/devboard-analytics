from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.dependencies import verify_internal_key
from app.schemas.events import ActivityEvent
from app.services.ingestion import record_event

router = APIRouter(prefix="/events", tags=["events"], dependencies=[Depends(verify_internal_key)])

@router.post("", response_model=ActivityEvent, status_code=201)
async def create_event(event: ActivityEvent, db: AsyncIOMotorDatabase = Depends(get_database)) -> ActivityEvent:  # noqa: B008
    return await record_event(event, db)
