#!/bin/bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Seed a workspace with default templates
# Usage: bash scripts/seed_workspace.sh [workspace_id]
set -e
cd "$(dirname "$0")/.."
WS="${1:-nexus_default}"
MEM_DIR="$HOME/clawos/memory/$WS"

mkdir -p "$MEM_DIR/preferences" "$MEM_DIR/knowledge" "$MEM_DIR/context"

copy_if_missing() {
  local src="$1" dst="$2"
  if [ ! -f "$dst" ]; then
    cp "$src" "$dst"
    echo "  [seed] $dst"
  else
    echo "  [skip] $dst (already exists)"
  fi
}

copy_if_missing "data/presets/workspaces/default/SOUL.md"      "$MEM_DIR/SOUL.md"
copy_if_missing "data/presets/workspaces/default/AGENTS.md"    "$MEM_DIR/AGENTS.md"
copy_if_missing "data/presets/workspaces/default/HEARTBEAT.md" "$MEM_DIR/HEARTBEAT.md"

if [ ! -f "$MEM_DIR/PINNED.md" ]; then
  echo "# Pinned Facts — edit to add permanent knowledge" > "$MEM_DIR/PINNED.md"
  echo "  [seed] $MEM_DIR/PINNED.md"
fi

echo "  Workspace '$WS' seeded at $MEM_DIR"
