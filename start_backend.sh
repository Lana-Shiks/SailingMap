#!/bin/bash
set -e

# Start the Router in the background
echo "Starting Router on port 8000..."
uvicorn services.router.main:app --host 127.0.0.1 --port 8000 &

# Start the Agent in the foreground
# Cloud Run provides the PORT environment variable (default is 8080)
PORT="${PORT:-8080}"
echo "Starting Agent on port $PORT..."
uvicorn agents.concierge_agent:app --host 0.0.0.0 --port $PORT
