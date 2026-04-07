#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Thin wrapper that forwards to the repo-root installer.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

exec bash "$REPO_ROOT/install.sh" "$@"
