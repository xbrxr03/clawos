"""
ClawOS Key Registry — single source of truth for all API keys.
Every key ClawOS knows about is defined here.
Any service that needs a key reads this registry.
"""

KEY_REGISTRY = [
    {
        "id":           "OPENROUTER_API_KEY",
        "label":        "OpenRouter",
        "description":  "Recommended — gives you 200+ models including Kimi k2.5, GPT-4o, Claude, Gemini",
        "url":          "https://openrouter.ai/keys",
        "required_for": ["openclaw"],
        "optional_for": ["nexus_cloud", "routing"],
        "placements": [
            {"type": "env",      "file": "~/.bashrc",                 "var": "OPENROUTER_API_KEY"},
            {"type": "env",      "file": "~/.zshrc",                  "var": "OPENROUTER_API_KEY"},
            {"type": "json_key", "file": "~/.openclaw/openclaw.json", "path": ["models", "providers", "openrouter", "apiKey"]},
            {"type": "secretd",  "key":  "openrouter_api_key"},
        ],
        "tier_shown": ["B", "C"],
    },
    {
        "id":           "OPENAI_API_KEY",
        "label":        "OpenAI (optional)",
        "description":  "Direct access to GPT-4o and o-series models",
        "url":          "https://platform.openai.com/api-keys",
        "required_for": [],
        "optional_for": ["openclaw", "nexus_cloud"],
        "placements": [
            {"type": "env",      "file": "~/.bashrc",                 "var": "OPENAI_API_KEY"},
            {"type": "env",      "file": "~/.zshrc",                  "var": "OPENAI_API_KEY"},
            {"type": "json_key", "file": "~/.openclaw/openclaw.json", "path": ["models", "providers", "openai", "apiKey"]},
            {"type": "secretd",  "key":  "openai_api_key"},
        ],
        "tier_shown": ["B", "C"],
    },
    {
        "id":           "ANTHROPIC_API_KEY",
        "label":        "Anthropic (optional)",
        "description":  "Direct access to Claude models",
        "url":          "https://console.anthropic.com/keys",
        "required_for": [],
        "optional_for": ["openclaw", "nexus_cloud"],
        "placements": [
            {"type": "env",      "file": "~/.bashrc",                 "var": "ANTHROPIC_API_KEY"},
            {"type": "env",      "file": "~/.zshrc",                  "var": "ANTHROPIC_API_KEY"},
            {"type": "json_key", "file": "~/.openclaw/openclaw.json", "path": ["models", "providers", "anthropic", "apiKey"]},
            {"type": "secretd",  "key":  "anthropic_api_key"},
        ],
        "tier_shown": ["B", "C"],
    },
    {
        "id":           "GROQ_API_KEY",
        "label":        "Groq (optional)",
        "description":  "Ultra-fast inference — Llama, Mixtral at very low cost",
        "url":          "https://console.groq.com/keys",
        "required_for": [],
        "optional_for": ["openclaw"],
        "placements": [
            {"type": "env",     "file": "~/.bashrc", "var": "GROQ_API_KEY"},
            {"type": "secretd", "key":  "groq_api_key"},
        ],
        "tier_shown": ["B", "C"],
    },
    {
        "id":           "ELEVENLABS_API_KEY",
        "label":        "ElevenLabs (optional)",
        "description":  "Premium voice synthesis — use instead of local Piper TTS",
        "url":          "https://elevenlabs.io/api",
        "required_for": [],
        "optional_for": ["voiced"],
        "placements": [
            {"type": "env",     "file": "~/.bashrc", "var": "ELEVENLABS_API_KEY"},
            {"type": "secretd", "key":  "elevenlabs_api_key"},
        ],
        "tier_shown": ["B", "C"],
    },
]
