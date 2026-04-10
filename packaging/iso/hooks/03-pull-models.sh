#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# ClawOS ISO hook 03 — Pull AI models into the ISO (baked-in)
# This runs during build, NOT on first boot — models ship with the ISO.
# For bandwidth reasons, only the default Tier B model is baked in.
# Tier A (ARM) gets qwen2.5:1.5b; skip on CI/low-disk builds.
set -uo pipefail

SKIP_MODELS="${SKIP_MODELS:-false}"
ARCH="$(uname -m)"

if [ "$SKIP_MODELS" = "true" ]; then
    echo "[ClawOS hook 03] SKIP_MODELS=true — skipping model pull (models will be pulled on first run)"
    exit 0
fi

echo "[ClawOS hook 03] Starting Ollama for model pull..."
ollama serve &
OLLAMA_PID=$!
sleep 5

pull_model() {
    local model="$1"
    echo "[hook 03] Pulling $model..."
    if ollama pull "$model"; then
        echo "[hook 03] ✓ $model ready"
    else
        echo "[hook 03] ⚠ Failed to pull $model (will be pulled on first run)"
    fi
}

# Choose model based on architecture
case "$ARCH" in
    aarch64|arm64|armv7l|armv8l)
        echo "[hook 03] ARM detected — pulling lightweight model"
        pull_model "qwen2.5:1.5b"
        ;;
    *)
        # x86_64 — pull standard Tier B model
        # Check available disk space (need ~6GB for qwen2.5:7b)
        DISK_FREE_GB=$(df / | awk 'NR==2 {print int($4/1048576)}')
        if [ "$DISK_FREE_GB" -ge 8 ]; then
            pull_model "qwen2.5:7b"
        elif [ "$DISK_FREE_GB" -ge 3 ]; then
            echo "[hook 03] Limited disk space (${DISK_FREE_GB}GB) — pulling 3b model"
            pull_model "qwen2.5:3b"
        else
            echo "[hook 03] Low disk space — skipping model bake-in"
        fi
        # Also pull embedding model
        pull_model "nomic-embed-text"
        ;;
esac

kill $OLLAMA_PID 2>/dev/null || true
echo "[hook 03] Model pull complete."
