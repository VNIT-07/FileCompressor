#!/bin/bash
# Start FileCompressor Web Interface
cd "$(dirname "$0")"
if [ -d ".venv" ]; then
    .venv/bin/python3 server.py "$@"
else
    python3 server.py "$@"
fi
