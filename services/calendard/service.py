# SPDX-License-Identifier: AGPL-3.0-or-later
"""
calendard — Calendar API Service
================================
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from services.calendard.engine import create_event, list_events, delete_event, CalendarEvent, export_ical

log = logging.getLogger("calendard")
router = APIRouter(prefix="/api/calendar", tags=["calendar"])


class CreateEventRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="")
    start_time: str = Field(default="")
    end_time: str = Field(default="")
    all_day: bool = Field(default=False)
    tags: Optional[list[str]] = None


@router.post("/create")
async def api_create_event(req: CreateEventRequest):
    event = create_event(title=req.title, description=req.description,
                         start_time=req.start_time, end_time=req.end_time,
                         all_day=req.all_day, tags=req.tags)
    return event.to_dict()


@router.get("/list")
async def api_list_events(from_date: str = None, to_date: str = None, tag: str = None):
    return list_events(from_date=from_date, to_date=to_date, tag=tag)


@router.get("/{event_id}")
async def api_get_event(event_id: str):
    event = CalendarEvent.load(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event.to_dict()


@router.delete("/{event_id}")
async def api_delete_event(event_id: str):
    ok = delete_event(event_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"deleted": True}


@router.get("/export/ical")
async def api_export_ical():
    return export_ical()