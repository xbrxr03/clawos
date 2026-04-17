# SPDX-License-Identifier: AGPL-3.0-or-later
"""
ClawOS omid — OMI Ambient AI Integration Service
=================================================

Processes webhooks from the OMI macOS app (BasedHardware):
  - Real-time transcript segments (passive capture + command detection)
  - Completed conversations (full memory pipeline + spoken reply)

Two modes (both active by default):
  1. Passive capture — all conversations stored silently in taosmd archive + KG + vector.
     Everything near your mic becomes searchable memory.
  2. Active response — "nexus, <command>" prefix triggers Nexus reply.
     OMI speaks the reply back via its TTS (ElevenLabs Sloane voice).

Works with:
  - OMI macOS app (macOS only — uses Mac mic, no hardware needed)
  - OMI wearable pendant (any OS — connects via phone app, sends webhooks)
  - Any client that POSTs OMI-format webhooks to localhost

Architecture:
  OMI app or pendant (mic + VAD + STT)
    ├── [real-time]  POST /api/omi/transcript  → command check → optional reply
    └── [on end]     POST /api/omi/conversation → full memory pipeline → summary reply
                                                      ↓
                                            taosmd archive ("omi_conversation")
                                            taosmd KG (triples from action items)
                                            vector memory (semantic search)
"""
import asyncio
import logging
import time
from collections import deque
from typing import Optional

from clawos_core.config.loader import get as get_config
from clawos_core.constants import DEFAULT_WORKSPACE, PORT_AGENTD

from services.omid.parser import (
    build_summary_prompt,
    extract_command,
    segments_to_kg_triples,
    segments_to_text,
)

log = logging.getLogger("omid")


class OmiService:
    """
    OMI webhook handler + memory pipeline.

    Both OMI and ClawOS run on the same machine, so webhooks hit localhost.
    No tunnels, no ngrok, no public URLs needed.
    """

    def __init__(self, workspace_id: str = DEFAULT_WORKSPACE):
        self.workspace_id = workspace_id
        self._conversations: deque[dict] = deque(maxlen=200)
        self._total_transcripts: int = 0
        self._total_conversations: int = 0
        self._last_event_ts: Optional[float] = None
        self._command_prefix: str = get_config("omi.command_prefix", "nexus")

    def handle_transcript(self, uid: str, segments: list[dict]) -> Optional[str]:
        """
        Handle real-time transcript webhook from OMI.

        OMI sends these during active listening with a 10s response timeout.
        We check for command prefix ("nexus, ...") and route to Nexus if found.
        Otherwise store passively and return None (no speak-back).

        Args:
            uid: OMI user/session identifier
            segments: List of transcript segment dicts

        Returns:
            Reply string if command detected (OMI speaks this),
            or None for passive capture (no speak-back).
        """
        self._total_transcripts += 1
        self._last_event_ts = time.time()

        if not segments:
            return None

        # Build text from user segments only for command detection
        user_text = segments_to_text(segments, user_only=True)
        if not user_text.strip():
            return None

        # Check for active command prefix
        command = extract_command(user_text)
        if command:
            log.info("OMI command detected from %s: %s", uid, command[:60])
            reply = self._route_to_nexus_sync(command)
            return reply

        # Passive mode — store in archive (non-blocking)
        if get_config("omi.passive_capture", True):
            full_text = segments_to_text(segments, user_only=False)
            self._store_transcript_async(full_text, uid)

        return None

    async def handle_conversation(self, uid: str, conversation: dict) -> str:
        """
        Handle conversation-end webhook from OMI.

        OMI sends this when a conversation finishes, with a 30s response timeout.
        We run the full memory pipeline and return a summary for OMI to speak.

        Args:
            uid: OMI user/session identifier
            conversation: Full OMI conversation payload with structured data

        Returns:
            Reply string for OMI to speak back to user.
        """
        self._total_conversations += 1
        self._last_event_ts = time.time()

        conv_id = conversation.get("id", f"omi-{int(time.time())}")
        structured = conversation.get("structured", {})
        segments = conversation.get("transcript_segments", [])
        title = structured.get("title", "Untitled conversation")

        log.info("OMI conversation ended: %s — %s", conv_id, title)

        # Extract full transcript
        full_text = segments_to_text(segments, user_only=False)
        if not full_text.strip():
            full_text = title

        # 1. Store in taosmd archive
        self._store_conversation(conv_id, conversation, full_text)

        # 2. Extract and store KG triples
        triples = segments_to_kg_triples(segments, structured)
        self._store_triples(triples)

        # 3. Store in vector memory for semantic search
        self._store_vector(full_text, conv_id, {
            "source": "omi",
            "title": title,
            "category": structured.get("category", ""),
        })

        # 4. Record in conversation history
        self._conversations.appendleft({
            "id": conv_id,
            "title": title,
            "category": structured.get("category", ""),
            "action_items": structured.get("action_items", []),
            "transcript_preview": full_text[:200],
            "timestamp": conversation.get("finished_at", time.strftime("%Y-%m-%dT%H:%M:%SZ")),
            "uid": uid,
            "triple_count": len(triples),
        })

        # 5. Generate summary reply via Nexus
        if get_config("omi.active_response", True):
            prompt = build_summary_prompt(full_text, structured)
            reply = await self._route_to_nexus_async(prompt)
            if reply:
                log.info("OMI reply for %s: %s", conv_id, reply[:80])
                return reply

        return f"Noted: {title}"

    def get_stats(self) -> dict:
        """Return OMI integration stats for dashboard/CLI."""
        base_url = get_config("omi.webhook_base_url", "http://localhost:7070")
        return {
            "enabled": get_config("omi.enabled", True),
            "total_transcripts": self._total_transcripts,
            "total_conversations": self._total_conversations,
            "last_event": self._last_event_ts,
            "stored_conversations": len(self._conversations),
            "passive_capture": get_config("omi.passive_capture", True),
            "active_response": get_config("omi.active_response", True),
            "command_prefix": self._command_prefix,
            "webhook_transcript": f"{base_url}/api/omi/transcript",
            "webhook_conversation": f"{base_url}/api/omi/conversation",
        }

    def list_conversations(self, limit: int = 20) -> list[dict]:
        """Return recent OMI conversations (newest first)."""
        return list(self._conversations)[:limit]

    def get_conversation(self, conv_id: str) -> Optional[dict]:
        """Get a specific conversation by ID."""
        for c in self._conversations:
            if c["id"] == conv_id:
                return c
        return None

    # ── Internal: memory storage ──────────────────────────────────────────────

    def _store_transcript_async(self, text: str, uid: str) -> None:
        """Store transcript text in archive (fire-and-forget)."""
        try:
            from services.memd.service import MemoryService
            mem = MemoryService()
            mem.remember(f"[OMI transcript from {uid}] {text[:500]}", self.workspace_id)
        except Exception as e:
            log.debug("Failed to store OMI transcript: %s", e)

    def _store_conversation(self, conv_id: str, conversation: dict, text: str) -> None:
        """Store full conversation in taosmd archive."""
        try:
            from services.memd.service import _get_archive
            archive = _get_archive()
            if archive:
                archive.record(
                    event_type="omi_conversation",
                    payload={
                        "id": conv_id,
                        "text": text[:4000],
                        "structured": conversation.get("structured", {}),
                        "source": conversation.get("source", "omi"),
                        "started_at": conversation.get("started_at", ""),
                        "finished_at": conversation.get("finished_at", ""),
                    },
                    agent_name="omid",
                )
        except Exception as e:
            log.debug("Failed to archive OMI conversation: %s", e)

    def _store_triples(self, triples: list[dict]) -> None:
        """Store KG triples from conversation."""
        try:
            from services.memd.service import _get_tkg
            tkg = _get_tkg()
            if tkg and triples:
                for t in triples:
                    tkg.add_triple(t["subject"], t["predicate"], t["object"])
        except Exception as e:
            log.debug("Failed to store OMI KG triples: %s", e)

    def _store_vector(self, text: str, memory_id: str, metadata: dict) -> None:
        """Store conversation text in vector memory for semantic search."""
        try:
            from services.memd.service import _get_vector
            vec = _get_vector()
            if vec:
                vec.add(text[:2000], memory_id=memory_id, metadata=metadata)
        except Exception as e:
            log.debug("Failed to store OMI vector memory: %s", e)

    # ── Internal: Nexus routing ───────────────────────────────────────────────

    def _route_to_nexus_sync(self, command: str) -> Optional[str]:
        """
        Send a command to Nexus via agentd HTTP API (synchronous).
        Used for real-time transcript commands where we have a 10s timeout.
        """
        try:
            import json
            import urllib.request

            url = f"http://127.0.0.1:{PORT_AGENTD}/submit"
            payload = json.dumps({
                "intent": command,
                "workspace": self.workspace_id,
                "channel": "omi",
                "session_id": f"omi-realtime-{int(time.time())}",
            }).encode()
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())
                return data.get("reply") or data.get("result") or str(data)
        except Exception as e:
            log.warning("Nexus routing failed for OMI command: %s", e)
            return None

    async def _route_to_nexus_async(self, prompt: str) -> Optional[str]:
        """
        Send a prompt to Nexus via agentd (async).
        Used for conversation summaries where we have a 30s timeout.
        """
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._route_to_nexus_sync, prompt)
        except Exception as e:
            log.warning("Async Nexus routing failed: %s", e)
            return None


# ── Singleton ─────────────────────────────────────────────────────────────────
_service: Optional[OmiService] = None


def get_service(workspace_id: str = DEFAULT_WORKSPACE) -> OmiService:
    """Get or create the singleton OmiService."""
    global _service
    if _service is None:
        _service = OmiService(workspace_id=workspace_id)
    return _service
