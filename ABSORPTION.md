# ClawOS Absorption Log

> Every external project, repo, algorithm, and research pattern that ClawOS integrates,
> wraps, or was inspired by. Full transparency.

ClawOS is a **curated integration layer**. We built the glue — Nexus, the memory system,
the workflow engine, the dashboard, the policy engine, the installer. But we stand on the
shoulders of dozens of open-source projects. This document tracks all of them.

---

## How to read this

- **Absorbed** = we pulled ideas, patterns, or code concepts from a repo and reimplemented
  them as native ClawOS services (AGPL-3.0 licensed, our code).
- **Integrated** = we install, configure, and orchestrate an external project as a dependency.
  Their code stays theirs, under their license.
- **Framework Store** = installable via `clawctl framework install <name>`. Not bundled —
  downloaded on demand. Their code, their license.
- **Research pattern** = algorithm or technique from published research, reimplemented from scratch.

---

## Core Runtime

| Project | Type | License | Repo | What ClawOS uses it for |
|---------|------|---------|------|-------------------------|
| **Ollama** | Integrated | MIT | [ollama/ollama](https://github.com/ollama/ollama) | Local LLM inference server. ClawOS auto-installs and manages it. Every local model runs through Ollama. |
| **OpenClaw** | Integrated | Custom | [openclaw/openclaw](https://github.com/openclaw/openclaw) | Optional advanced agent runtime with 13,700+ community skills. ClawOS pre-configures it for offline use and routes JARVIS voice through it. |
| **LiteLLM** | Integrated | MIT | [BerriAI/litellm](https://github.com/BerriAI/litellm) | Unified API gateway (`services/llmd/`). Routes requests to Ollama, Anthropic, OpenAI, Azure through one endpoint. Port 11500. |

## Voice & Audio Pipeline

| Project | Type | License | Repo | What ClawOS uses it for |
|---------|------|---------|------|-------------------------|
| **OpenAI Whisper** | Integrated | MIT | [openai/whisper](https://github.com/openai/whisper) | Speech-to-text transcription. Runs locally, no API key. `adapters/audio/whisper_adapter.py` |
| **faster-whisper** | Integrated | MIT | [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) | 4x faster Whisper alternative using CTranslate2. Used when available, falls back to standard Whisper. |
| **Piper TTS** | Integrated | MIT | [rhasspy/piper](https://github.com/rhasspy/piper) | Offline text-to-speech. Default JARVIS voice (free tier). `adapters/audio/tts_router.py` |
| **OpenWakeWord** | Integrated | Apache 2.0 | [dscripka/openWakeWord](https://github.com/dscripka/openWakeWord) | Wake word detection ("Hey Jarvis"). Runs in `services/voiced/wake.py` with pre-trained ONNX model. |
| **ElevenLabs** | Integrated | Proprietary API | [elevenlabs.io](https://elevenlabs.io) | Premium JARVIS voice (paid tier). User provides their own API key. `adapters/audio/elevenlabs_adapter.py` |
| **OMI** | Integrated | MIT | [BasedHardware/omi](https://github.com/BasedHardware/omi) | Ambient AI — macOS app or wearable pendant captures conversations, sends webhooks to `services/omid/`. Passive memory capture + "nexus, ..." active commands. |

## Memory System (taosmd)

The 14-layer memory system in `services/memd/taosmd/` was **absorbed** — reimplemented as
native ClawOS code (AGPL-3.0) based on patterns from multiple research sources.

| Component | Type | Origin | What it does in ClawOS |
|-----------|------|--------|------------------------|
| **Temporal Knowledge Graph** | Research pattern | Temporal RDF / knowledge graph research | `knowledge_graph.py` — SQLite-backed KG with validity windows (`valid_from`, `valid_until`), contradiction detection for exclusive predicates. Point-in-time queries. |
| **Ebbinghaus Retention Decay** | Research pattern | Hermann Ebbinghaus (1885) forgetting curve | `retention.py` — `R = e^(-elapsed/stability)`. Stability grows with each access. 4 tiers: HOT/WARM/COLD/EVICTABLE. Prevents memory bloat. |
| **RRF (Reciprocal Rank Fusion)** | Research pattern | Cormack et al. (2009) | `vector_memory.py` — Merges semantic (ChromaDB) + keyword (FTS5) results: `score = 1/(60+rank_sem) + 1/(60+rank_kw)`. |
| **Jaccard Deduplication** | Research pattern | Set similarity (classical) | `vector_memory.py` — Token-level Jaccard at 0.8 threshold to prevent near-duplicate memories. |
| **Secret Redaction** | Absorbed | Common security patterns | `secret_filter.py` — 17 compiled regex patterns. Redacts API keys, tokens, passwords, credit cards before storage. |
| **Intent-Routed Retrieval** | Absorbed | Query classification research | `intent_classifier.py` — 7 intent types (FACTUAL, RECENT, TECHNICAL, etc.) route to appropriate backends (archive, KG, vector). |
| **Daily JSONL Archive** | Absorbed | Append-only log patterns | `archive.py` — Write to `YYYY-MM-DD.jsonl`, FTS5 index for search, gzip compression for old files. |

### Memory dependencies

| Project | Type | License | Repo | Role |
|---------|------|---------|------|------|
| **ChromaDB** | Integrated | Apache 2.0 | [chroma-core/chroma](https://github.com/chroma-core/chroma) | Vector database for semantic search layer. |
| **SQLite FTS5** | Built-in | Public domain | Part of Python stdlib | Keyword search layer + archive index. |

## RAG & Retrieval

| Project | Type | License | Repo | What ClawOS uses it for |
|---------|------|---------|------|-------------------------|
| **CrossEncoder (MS MARCO)** | Integrated | Apache 2.0 | [cross-encoder/ms-marco-MiniLM-L-6-v2](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L-6-v2) | Reranking in `services/ragd/service.py`. Threshold 0.7, top-10 candidates. Graceful skip if unavailable. |
| **sentence-transformers** | Integrated | Apache 2.0 | [UKPLab/sentence-transformers](https://github.com/UKPLab/sentence-transformers) | Hosts the CrossEncoder model. |
| **GraphRAG pattern** | Research pattern | Microsoft Research | `services/braind/` — Knowledge graph retrieval augmented generation. Community detection + gap analysis. |

## Knowledge Graph & Brain

| Project | Type | License | Repo | What ClawOS uses it for |
|---------|------|---------|------|-------------------------|
| **NetworkX** | Integrated | BSD | [networkx/networkx](https://github.com/networkx/networkx) | Graph algorithms for the 3D knowledge brain (`services/braind/`). |
| **CDlib** | Integrated | BSD | [GiulioRossetti/CDlib](https://github.com/GiulioRossetti/CDlib) | Leiden community detection in knowledge graphs. |
| **react-force-graph-3d** | Integrated | MIT | [vasturiano/react-force-graph](https://github.com/vasturiano/react-force-graph) | 3D force-directed graph visualization in the Brain dashboard page. |
| **Three.js** | Integrated | MIT | [mrdoob/three.js](https://github.com/mrdoob/three.js) | WebGL renderer for the 3D knowledge graph with UnrealBloom glow. |

## Browser Automation

| Project | Type | License | Repo | What ClawOS uses it for |
|---------|------|---------|------|-------------------------|
| **Playwright** | Integrated | Apache 2.0 | [microsoft/playwright](https://github.com/microsoft/playwright) | Headless Chromium browser control. Policy-gated — every action requires approval. `adapters/browser/playwright_adapter.py` |

## Framework Store (9 installable frameworks)

These are **not bundled** with ClawOS. They are downloaded on demand via
`clawctl framework install <name>`. Each runs as its own process with an
OpenAI-compatible API that ClawOS routes through.

| Framework | Repo | What it is |
|-----------|------|------------|
| **SmolAgents** | [huggingface/smolagents](https://github.com/huggingface/smolagents) | HuggingFace code-based agent. Writes and executes Python directly instead of JSON tool calling. 30% fewer LLM calls. |
| **AgentZero** | [frdel/agent-zero](https://github.com/frdel/agent-zero) | Autonomous agent with self-correcting workflows, dynamic tool creation, and computer control (mouse/keyboard/screen). |
| **PocketFlow** | [The-Pocket/PocketFlow](https://github.com/The-Pocket/PocketFlow) | 100-line LLM framework. Zero dependencies. Graph-based agent pipelines with native MCP support. |
| **Langroid** | [langroid/langroid](https://github.com/langroid/langroid) | Multi-agent message-passing framework with built-in vector store and local LLM support. |
| **OpenAI Agents SDK** | [openai/openai-agents-python](https://github.com/openai/openai-agents-python) | Provider-agnostic multi-agent framework with tracing, guardrails, and LiteLLM routing. |
| **NullClaw** | [nullclaw/nullclaw](https://github.com/nullclaw/nullclaw) | Stateless ephemeral agent. No persistent state, pure function execution. |
| **ZeroClaw** | [zeroclaw/zeroclaw](https://github.com/zeroclaw/zeroclaw) | Rust implementation. 99% memory reduction vs Python agents. Ultra-lightweight. |
| **NanoClaw** | [nanoclaw/nanoclaw](https://github.com/nanoclaw/nanoclaw) | ~500 TypeScript lines. Proves agents don't need hundreds of MB of RAM. |
| **OpenClaw** | [openclaw/openclaw](https://github.com/openclaw/openclaw) | Full-featured runtime with 13,700+ community skills and multi-channel support. |

## Lightweight Runtimes

| Project | Type | License | Repo | What ClawOS uses it for |
|---------|------|---------|------|-------------------------|
| **PicoClaw** | Integrated | Unknown | [sipeed/picoclaw](https://github.com/sipeed/picoclaw) | Tier A (ARM) lightweight agent runtime. Auto-enabled on ARM hardware. |

## Search & APIs

| Service | Type | What ClawOS uses it for |
|---------|------|-------------------------|
| **Brave Search API** | Optional API | Web search in research engine + JARVIS briefings. User provides API key. |
| **Tavily Search API** | Optional API | Alternative search provider for research engine. |
| **DuckDuckGo** | Integrated | Fallback web search (no API key required). |
| **Open-Meteo** | Integrated (free) | Weather data for JARVIS morning briefings. No API key. |
| **Google Calendar (ICS)** | Integrated | Calendar events for JARVIS briefings. User provides ICS URL. |

## Web Framework & Infrastructure

| Project | License | Repo | Role |
|---------|---------|------|------|
| **FastAPI** | MIT | [tiangolo/fastapi](https://github.com/tiangolo/fastapi) | REST API + WebSocket server for all services |
| **Uvicorn** | BSD | [encode/uvicorn](https://github.com/encode/uvicorn) | ASGI server |
| **React** | MIT | [facebook/react](https://github.com/facebook/react) | Dashboard frontend (17 pages) |
| **Vite** | MIT | [vitejs/vite](https://github.com/vitejs/vite) | Frontend build tooling |
| **Tailwind CSS** | MIT | [tailwindlabs/tailwindcss](https://github.com/tailwindlabs/tailwindcss) | Dashboard styling |
| **React Router** | MIT | [remix-run/react-router](https://github.com/remix-run/react-router) | Frontend routing |

## Document Processing

| Project | License | Repo | Role |
|---------|---------|------|------|
| **pdfplumber** | MIT | [jsvine/pdfplumber](https://github.com/jsvine/pdfplumber) | PDF text/table extraction for summarize-pdf workflow |
| **python-docx** | MIT | [python-openxml/python-docx](https://github.com/python-openxml/python-docx) | Word document reading |
| **icalendar** | BSD | [collective/icalendar](https://github.com/collective/icalendar) | ICS calendar parsing for JARVIS briefings |

## CLI & Utilities

| Project | License | Repo | Role |
|---------|---------|------|------|
| **Click** | BSD | [pallets/click](https://github.com/pallets/click) | `clawctl` CLI framework |
| **PyYAML** | MIT | [yaml/pyyaml](https://github.com/yaml/pyyaml) | Configuration file parsing |
| **cryptography** | Apache 2.0 / BSD | [pyca/cryptography](https://github.com/pyca/cryptography) | Ed25519 skill signing, credential encryption, Merkle audit logs |
| **json-repair** | MIT | [jorenretel/json_repair](https://github.com/jorenretel/json_repair) | Malformed LLM JSON output repair |
| **LangChain** | MIT | [langchain-ai/langchain](https://github.com/langchain-ai/langchain) | Experimental utilities for brain/knowledge graph service |

## Security Features (original ClawOS)

These are **not absorbed** — they are original ClawOS implementations:

- **policyd** — Merkle-tree audit trail, risk scoring, human approval queue
- **Ed25519 skill signing** — prevents supply chain attacks on skill marketplace
- **Typosquatting protection** — Levenshtein distance check against 18 known-safe names
- **Secret redaction** — 17 regex patterns strip credentials before memory storage
- **Session cookie rotation** — dashboard auth rotates after setup completion

## What ClawOS built from scratch

For the record, these are **100% original** ClawOS code (AGPL-3.0):

| Service | What it does |
|---------|-------------|
| `services/memd/` | Memory service — 14-layer architecture, taosmd integration |
| `services/dashd/` | Dashboard API — 100+ REST endpoints, WebSocket snapshots |
| `services/policyd/` | Policy engine — risk scoring, approval queue, Merkle audit |
| `services/gatewayd/` | Gateway — WhatsApp bridge, framework routing, media handling |
| `services/jarvisd/` | JARVIS — voice personality, briefings, OpenClaw brain bridge |
| `services/omid/` | OMI integration — ambient capture, command detection, KG extraction |
| `services/frameworkd/` | Framework Store — install/start/stop/activate lifecycle |
| `services/llmd/` | LLM proxy — unified routing to Ollama + cloud providers |
| `services/ragd/` | RAG service — document retrieval with CrossEncoder reranking |
| `services/braind/` | Knowledge graph — 3D brain with community detection |
| `services/agentd/` | Agent orchestrator — task queue, runtime dispatch |
| `services/toolbridge/` | Tool execution — sandboxed, policy-gated |
| `services/voiced/` | Voice pipeline — wake word, STT, TTS orchestration |
| `services/scheduler/` | Workflow scheduler — cron-style automation engine |
| `runtimes/agent/` | Nexus runtime — ReAct loop, ACE self-improvement, IDENTITY |
| `workflows/` | 29 workflow programs — deterministic + LLM-assisted |
| `dashboard/frontend/` | 17-page React command center |
| `clawctl/` | CLI — 60+ commands across 15 command groups |
| `bootstrap/` | First-run wizard, hardware probe, model provisioning |
| `install.sh` | One-command installer with 4-tier hardware detection |
| `landing/` | Marketing landing page |

---

## License compliance

- ClawOS itself is **AGPL-3.0-or-later**. Every `.py` file has SPDX headers.
- All integrated dependencies are used under their respective licenses (MIT, Apache 2.0, BSD, etc.).
- Framework Store entries are downloaded on demand, not bundled. Their licenses are theirs.
- No proprietary code is included. ElevenLabs is an optional API — user provides their own key.
- OpenClaw is an optional runtime — ClawOS works fully without it.

---

*Last updated: 2026-04-16*
