#!/usr/bin/env bash
# Write Vite env pointing at the WSL backend (Windows localhost:8000 often does not reach WSL).
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WSL_IP="$(hostname -I | awk '{print $1}')"
ENV_FILE="${PROJECT_DIR}/acds/ui/frontend/.env.development.local"

cat > "${ENV_FILE}" <<EOF
# Auto-generated — WSL backend URL for Windows browser
VITE_API_BASE=http://${WSL_IP}:8000
VITE_WS_URL=ws://${WSL_IP}:8000/ws/telemetry
VITE_GRAPH_API=http://${WSL_IP}:8100
EOF

echo "Wrote ${ENV_FILE} (API → http://${WSL_IP}:8000, Graph → http://${WSL_IP}:8100)"
