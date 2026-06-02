# SPDX-License-Identifier: AGPL-3.0-or-later
"""
maild — Email API Service
=========================
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from services.maild.engine import check_mail, send_mail, MailConfig

log = logging.getLogger("maild")
router = APIRouter(prefix="/api/mail", tags=["mail"])


class SendRequest(BaseModel):
    to: str = Field(..., min_length=3)
    subject: str = Field(..., min_length=1)
    body: str = Field(default="")


@router.get("/inbox")
async def api_inbox(limit: int = 20):
    """Check inbox via IMAP."""
    messages = check_mail(limit=limit)
    return {"messages": [m.to_dict() for m in messages], "count": len(messages)}


@router.post("/send")
async def api_send(req: SendRequest):
    """Send email via SMTP."""
    ok = send_mail(to=req.to, subject=req.subject, body=req.body)
    if not ok:
        raise HTTPException(status_code=500, detail="Send failed — check mail config")
    return {"sent": True}


@router.get("/config")
async def api_config():
    """Check if mail is configured."""
    cfg = MailConfig.load()
    return {
        "configured": bool(cfg.imap_host and cfg.username),
        "imap_host": cfg.imap_host,
        "smtp_host": cfg.smtp_host,
        "username": cfg.username,
    }