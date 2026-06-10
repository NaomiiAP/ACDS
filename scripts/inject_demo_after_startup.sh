#!/usr/bin/env bash
# Wait for graph service + Kafka, then inject demo ML alerts (same as manual inject_demo_alerts.py).
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/venv.sh
source "${PROJECT_DIR}/scripts/venv.sh"

WAIT_SEC="${ACDS_DEMO_INJECT_WAIT:-25}"
GRAPH_PORT="${GRAPH_API_PORT:-8100}"

echo "Waiting ${WAIT_SEC}s for graph service (port ${GRAPH_PORT}) and Kafka..."
sleep "${WAIT_SEC}"

for i in $(seq 1 15); do
    if curl -sf "http://127.0.0.1:${GRAPH_PORT}/api/graph/summary" >/dev/null 2>&1; then
        echo "Graph service is up."
        break
    fi
    echo "  Graph not ready yet (${i}/15)..."
    sleep 2
done

echo "Injecting demo alerts into ml.alerts..."
cd "${PROJECT_DIR}"
export PYTHONPATH="${PROJECT_DIR}"
"${ACDS_VENV_PY}" scripts/inject_demo_alerts.py
echo "Done — refresh the Attack Graph page."
