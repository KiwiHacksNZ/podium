#!/bin/bash

set -e

# Install concurrently if not present
if ! command -v concurrently &> /dev/null; then
  echo "Installing concurrently..."
  npm install -g concurrently
fi

echo "Starting backend and frontend..."

# Secrets are loaded from backend/.env by Dynaconf (see .env.example).
concurrently -n "BACKEND,FRONTEND" -c "cyan,yellow" \
  "cd backend && uv run podium" \
  "cd frontend && bun dev"
