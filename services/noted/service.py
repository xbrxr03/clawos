# SPDX-License-Identifier: AGPL-3.0-or-later
"""
noted — Notes API Service
==========================
FastAPI service for local-first note-taking.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.noted.engine import create_note, list_notes, delete_note, Note

log = logging.getLogger("noted")
router = APIRouter(prefix="/api/notes", tags=["notes"])


class CreateNoteRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(default="")
    tags: Optional[list[str]] = Field(default=None)


class UpdateNoteRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[list[str]] = None


@router.post("/create")
async def api_create_note(req: CreateNoteRequest):
    note = create_note(title=req.title, content=req.content, tags=req.tags)
    return note.to_dict()


@router.get("/list")
async def api_list_notes(tag: str = None, search: str = None):
    return list_notes(tag=tag, search=search)


@router.get("/{note_id}")
async def api_get_note(note_id: str):
    note = Note.load(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note.to_dict()


@router.put("/{note_id}")
async def api_update_note(note_id: str, req: UpdateNoteRequest):
    note = Note.load(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    if req.title is not None:
        note.title = req.title
    if req.content is not None:
        note.content = req.content
    if req.tags is not None:
        note.tags = req.tags
    note.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    note.save()
    return note.to_dict()


@router.delete("/{note_id}")
async def api_delete_note(note_id: str):
    ok = delete_note(note_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"deleted": True}


import time  # noqa: E402
