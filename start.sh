#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# start.sh – Run the Restaurant Voice Agent backend.
# Always execute this from the PROJECT ROOT, not from inside backend/.
#
# Usage:
#   cd /home/uzwalpandey/Documents/resturent_voice
#   conda activate voice
#   bash start.sh
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# Ensure we are in the project root (directory that contains this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Copy .env.example → .env if .env doesn't exist yet
if [ ! -f .env ]; then
  echo "⚠  No .env found – copying .env.example to .env"
  cp .env.example .env
fi

# Add project root to PYTHONPATH so `from backend.xxx import ...` works
export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}"

echo "🚀 Starting FastAPI server from: $SCRIPT_DIR"
echo "   PYTHONPATH=$PYTHONPATH"
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
