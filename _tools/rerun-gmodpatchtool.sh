#!/usr/bin/env bash
set -euo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STEAM_ROOT="${STEAM_ROOT:-$HOME/.steam/steam}"
cd "$SELF/_tools/GModPatchTool"
exec ./gmodpatchtool --skip-exit-prompt --ignore-gmod-running --steam-path "$STEAM_ROOT"
