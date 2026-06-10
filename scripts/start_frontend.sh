#!/usr/bin/env bash
export PATH="/mnt/d/Program Files/nodejs:$PATH"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
bash "${SCRIPT_DIR}/write_frontend_env.sh"
cd "${PROJECT_DIR}/acds/ui/frontend"
mkdir -p "${PROJECT_DIR}/.service_logs"
pkill -f "vite.*5173" 2>/dev/null || true
exec npm run dev -- --host 0.0.0.0 --port 5173
