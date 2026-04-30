# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Wake Word Trigger Service (waketrd)
====================================
Bridges voiced wake word detection to Nexus morning briefing.

When "Hey JARVIS" is detected:
1. Call /api/wake to jarvisd or directly invoke briefing
2. Wait for follow-up audio
3. Route to appropriate handler
"""
import asyncio
import json
import logging
import time
from typing import Optional

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from clawos_core.constants import CLAWOS_DIR, PORT_VOICED, DEFAULT_WORKSPACE
from runtimes.agent.voice_entry import speak_morning_briefing
from adapters.audio.tts_router import speak as tts_speak

log = logging.getLogger("waketrd")

# State tracking
last_wake_time: float = 0
WAKE_COOLDOWN_SECONDS = 3  # Prevent duplicate triggers

app = FastAPI(title="Wake Word Trigger", version="1.0.0")


@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "healthy",
        "service": "waketrd",
        "voiced_port": PORT_VOICED,
        "last_wake": last_wake_time if last_wake_time else None,
    }


@app.post("/trigger")
async def trigger_wake(
    follow_up: Optional[str] = None,
    workspace_id: str = DEFAULT_WORKSPACE,
):
    """
    Triggered when wake word is detected.
    
    Args:
        follow_up: Optional transcribed text after wake word
        workspace_id: Target workspace
    """
    global last_wake_time
    
    now = time.time()
    if now - last_wake_time < WAKE_COOLDOWN_SECONDS:
        log.debug("Wake word cooldown, ignoring")
        return {"triggered": False, "reason": "cooldown"}
    
    last_wake_time = now
    
    # Check for briefing intent in follow-up
    briefing_triggers = [
        "what's up", "whats up", "what is up",
        "good morning", "morning",
        "brief me", "briefing",
        "what's my day", "what is my day",
        "catch me up",
        "what do i have",
        "what's going on", "what is going on",
        "day update",
    ]
    
    is_briefing_request = False
    if follow_up:
        follow_lower = follow_up.lower()
        is_briefing_request = any(t in follow_lower for t in briefing_triggers)
    
    try:
        if is_briefing_request or not follow_up:
            # Deliver morning briefing
            log.info("Wake word triggered morning briefing")
            
            async def tts_fn(text: str):
                await tts_speak(text)
            
            briefing_text = await speak_morning_briefing(
                tts_fn=tts_fn,
                workspace_id=workspace_id,
            )
            
            return {
                "triggered": True,
                "action": "morning_briefing",
                "spoken": True,
                "text": briefing_text,
            }
        else:
            # Regular voice chat
            log.info(f"Wake word triggered chat: {follow_up}")
            
            from runtimes.agent.voice_entry import voice_chat_once
            
            async def tts_fn(text: str):
                await tts_speak(text)
            
            reply = await voice_chat_once(
                user_text=follow_up,
                tts_fn=tts_fn,
                workspace_id=workspace_id,
            )
            
            return {
                "triggered": True,
                "action": "voice_chat",
                "spoken": True,
                "reply": reply,
            }
            
    except Exception as e:
        log.error(f"Wake word handling failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/voiced-webhook")
async def voiced_webhook(payload: dict):
    """
    Webhook endpoint for voiced to call when wake word detected.
    
    Expected payload:
    {
        "event": "wake_word_detected",
        "timestamp": 1234567890,
        "audio_data": "...",  # Optional follow-up audio
        "confidence": 0.95
    }
    """
    event = payload.get("event")
    
    if event == "wake_word_detected":
        return await trigger_wake()
    elif event == "wake_word_with_followup":
        follow_up = payload.get("transcribed_text", "")
        return await trigger_wake(follow_up=follow_up)
    else:
        return {"triggered": False, "reason": f"unknown event: {event}"}


# Lifespan context manager for modern FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events - startup and shutdown."""
    log.info("Wake trigger service starting")
    yield
    log.info("Wake trigger service stopping")

# Re-create app with lifespan
app = FastAPI(title="Wake Word Trigger", version="1.0.0", lifespan=lifespan)

@app.get("/health")
async def health_v2():
    """Health check."""
    return {
        "status": "healthy",
        "service": "waketrd",
        "voiced_port": PORT_VOICED,
        "last_wake": last_wake_time if last_wake_time else None,
    }


@app.post("/trigger")
async def trigger_wake_v2(
    follow_up: Optional[str] = None,
    workspace_id: str = DEFAULT_WORKSPACE,
):
    """Trigger wake word handling."""
    global last_wake_time
    
    now = time.time()
    if now - last_wake_time < WAKE_COOLDOWN_SECONDS:
        return {"triggered": False, "reason": "cooldown"}
    
    last_wake_time = now
    
    briefing_triggers = [
        "what's up", "whats up", "what is up",
        "good morning", "morning",
        "brief me", "briefing",
        "what's my day", "what is my day",
        "catch me up",
        "what do i have",
        "what's going on", "what is going on",
        "day update",
    ]
    
    is_briefing_request = False
    if follow_up:
        follow_lower = follow_up.lower()
        is_briefing_request = any(t in follow_lower for t in briefing_triggers)
    
    try:
        if is_briefing_request or not follow_up:
            log.info("Wake word triggered morning briefing")
            
            async def tts_fn(text: str):
                await tts_speak(text)
            
            briefing_text = await speak_morning_briefing(
                tts_fn=tts_fn,
                workspace_id=workspace_id,
            )
            
            return {
                "triggered": True,
                "action": "morning_briefing",
                "spoken": True,
                "text": briefing_text,
            }
        else:
            log.info(f"Wake word triggered chat: {follow_up}")
            
            from runtimes.agent.voice_entry import voice_chat_once
            
            async def tts_fn(text: str):
                await tts_speak(text)
            
            reply = await voice_chat_once(
                user_text=follow_up,
                tts_fn=tts_fn,
                workspace_id=workspace_id,
            )
            
            return {
                "triggered": True,
                "action": "voice_chat",
                "spoken": True,
                "reply": reply,
            }
            
    except Exception as e:
        log.error(f"Wake word handling failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/voiced-webhook")
async def voiced_webhook_v2(payload: dict):
    """Webhook from voiced service."""
    event = payload.get("event")
    
    if event == "wake_word_detected":
        return await trigger_wake_v2()
    elif event == "wake_word_with_followup":
        follow_up = payload.get("transcribed_text", "")
        return await trigger_wake_v2(follow_up=follow_up)
    else:
        return {"triggered": False, "reason": f"unknown event: {event}"}


def main():
    """Entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    
    # Use a new port
    PORT_WAKETRD = 7088
    uvicorn.run(app, host="127.0.0.1", port=PORT_WAKETRD)


if __name__ == "__main__":
    main()
