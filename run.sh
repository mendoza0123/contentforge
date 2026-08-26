#!/bin/bash
# ContentForge — Development Server
set -e

cd "$(dirname "$0")"

# Use existing venv if available, otherwise create one
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -f "../marketing-agent/venv/bin/activate" ]; then
    source ../marketing-agent/venv/bin/activate
fi

# Install deps if needed
pip install -r requirements.txt -q 2>/dev/null || true

# Run
echo "🚀 ContentForge starting at http://0.0.0.0:8000"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload