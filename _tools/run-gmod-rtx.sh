#!/usr/bin/env bash
set -euo pipefail
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$SELF/launch-gmod-rtx.sh" "$@"
