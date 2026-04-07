# SPDX-License-Identifier: AGPL-3.0-or-later
#!/usr/bin/env python3
"""Query ClawOS RAGd service from OpenClaw skill."""
import json
import sys
import urllib.request

from clawos_core.service_manager import service_hint


def main():
    if len(sys.argv) < 2:
        print("Usage: rag_query.py <question>")
        sys.exit(1)
    query = " ".join(sys.argv[1:])
    payload = json.dumps({
        "id": "openclaw-query",
        "message": {"parts": [{"type": "text", "text": query}]},
    }).encode()
    try:
        req = urllib.request.Request(
            "http://localhost:7082/a2a/tasks/send",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read())
            text = (result.get("artifacts", [{}])[0]
                         .get("parts", [{}])[0]
                         .get("text", "No answer"))
            print(text)
    except Exception as e:
        print(f"[RAGd unavailable: {e}]")
        print(f"Ensure ClawOS services are running: {service_hint('start', 'clawos.service')}")


if __name__ == "__main__":
    main()
