# SPDX-License-Identifier: AGPL-3.0-or-later
"""
clawctl omi — OMI ambient AI integration commands.

  clawctl omi status   — show webhook URL + last event + conversation count
  clawctl omi history  — list recent OMI conversations from archive
  clawctl omi show <id> — show full conversation detail
  clawctl omi setup    — print the URL to paste into OMI app settings
"""
import json
import sys
import time


def run_status():
    """Show OMI integration status."""
    try:
        from services.omid.service import get_service
        stats = get_service().get_stats()
    except (ImportError, ModuleNotFoundError) as e:
        print(f"OMI service not available: {e}")
        return

    print("OMI Integration Status")
    print("=" * 40)
    print(f"  Enabled:            {stats['enabled']}")
    print(f"  Passive capture:    {stats['passive_capture']}")
    print(f"  Active response:    {stats['active_response']}")
    print(f"  Command prefix:     \"{stats['command_prefix']}\"")
    print()
    print(f"  Transcripts:        {stats['total_transcripts']}")
    print(f"  Conversations:      {stats['total_conversations']}")
    print(f"  Stored:             {stats['stored_conversations']}")
    if stats["last_event"]:
        elapsed = int(time.time() - stats["last_event"])
        print(f"  Last event:         {elapsed}s ago")
    else:
        print("  Last event:         (none)")
    print()
    print("Webhook URLs:")
    print(f"  Transcript:  {stats['webhook_transcript']}")
    print(f"  Conversation: {stats['webhook_conversation']}")


def run_history(limit: int = 20):
    """List recent OMI conversations."""
    try:
        from services.omid.service import get_service
        conversations = get_service().list_conversations(limit)
    except (ImportError, ModuleNotFoundError) as e:
        print(f"OMI service not available: {e}")
        return

    if not conversations:
        print("No OMI conversations recorded yet.")
        print("Say something near your OMI device to start capturing.")
        return

    print(f"Recent OMI Conversations ({len(conversations)})")
    print("-" * 60)
    for c in conversations:
        ts = c.get("timestamp", "?")
        title = c.get("title", "Untitled")
        cat = c.get("category", "")
        actions = len(c.get("action_items", []))
        triples = c.get("triple_count", 0)
        cat_str = f" [{cat}]" if cat else ""
        action_str = f" ({actions} actions)" if actions else ""
        print(f"  {c['id'][:16]}  {ts[:19]}  {title[:40]}{cat_str}{action_str}")


def run_show(conv_id: str):
    """Show detail for a specific OMI conversation."""
    try:
        from services.omid.service import get_service
        conv = get_service().get_conversation(conv_id)
    except (ImportError, ModuleNotFoundError) as e:
        print(f"OMI service not available: {e}")
        return

    if not conv:
        # Try partial match
        try:
            from services.omid.service import get_service
            all_convs = get_service().list_conversations(200)
            matches = [c for c in all_convs if c["id"].startswith(conv_id)]
            if len(matches) == 1:
                conv = matches[0]
            elif len(matches) > 1:
                print(f"Ambiguous ID '{conv_id}'. Matches:")
                for m in matches:
                    print(f"  {m['id']}")
                return
        except (ImportError, ModuleNotFoundError):
            pass
            pass

    if not conv:
        print(f"Conversation '{conv_id}' not found.")
        return

    print(f"OMI Conversation: {conv['id']}")
    print("=" * 50)
    print(f"  Title:      {conv.get('title', '?')}")
    print(f"  Category:   {conv.get('category', '?')}")
    print(f"  Timestamp:  {conv.get('timestamp', '?')}")
    print(f"  UID:        {conv.get('uid', '?')}")
    print(f"  KG Triples: {conv.get('triple_count', 0)}")

    actions = conv.get("action_items", [])
    if actions:
        print(f"\n  Action Items ({len(actions)}):")
        for a in actions:
            print(f"    - {a}")

    preview = conv.get("transcript_preview", "")
    if preview:
        print(f"\n  Transcript Preview:")
        print(f"    {preview}")


def run_setup():
    """Print OMI setup instructions with webhook URLs."""
    try:
        from clawos_core.config.loader import get as get_config
        base_url = get_config("omi.webhook_base_url", "http://localhost:7070")
    except (ImportError, ModuleNotFoundError):
        base_url = "http://localhost:7070"

    print()
    print("OMI Integration Setup")
    print("=" * 50)
    print()
    print("In the OMI macOS app:")
    print("  Settings > Plugins > Add Custom Plugin")
    print()
    print(f"  Transcript Webhook:   {base_url}/api/omi/transcript")
    print(f"  Conversation Webhook: {base_url}/api/omi/conversation")
    print()
    print("Platform support:")
    print("  - OMI macOS app: runs on the same Mac as ClawOS (localhost)")
    print("  - OMI wearable pendant: connects via phone app, works with any OS")
    print("    (set webhook URL to your machine's LAN IP instead of localhost)")
    print()
    print("To test: say something. OMI will send the transcript to ClawOS.")
    print("ClawOS stores it in memory. Say \"nexus, <question>\" to get a")
    print("spoken reply.")
    print()
    print("Modes:")
    print("  Passive — all conversations stored silently in memory.")
    print("            Ask Nexus later: \"what did I discuss with Bob today?\"")
    print("  Active  — say \"nexus, ...\" and OMI speaks Nexus's reply back.")
    print()
    print("Note: OMI is optional. ClawOS JARVIS voice (wake word + Whisper +")
    print("Piper/ElevenLabs) works on all platforms without OMI.")
    print()
