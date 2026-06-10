#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
source "${SCRIPT_DIR}/venv.sh"

echo "========== ACDS Telemetry Diagnostics =========="
echo ""

echo "[1] System bcc (eBPF):"
if python3 -c "import bcc" 2>/dev/null; then echo "  OK - bcc importable"; else echo "  FAIL - run: bash scripts/ensure_system_deps.sh"; fi

echo "[2] libpcap (DPI):"
if ldconfig -p 2>/dev/null | grep -q libpcap.so; then echo "  OK"; else echo "  FAIL - sudo apt install libpcap-dev"; fi

echo "[3] Running processes:"
pgrep -af "agent.py|uvicorn server|generate_traffic" 2>/dev/null | grep -v diagnose || echo "  NONE - services not running"

echo "[4] Backend API:"
if curl -sf http://127.0.0.1:8000/api/status >/tmp/acds_status.json 2>/dev/null; then
    python3 -c "import json; d=json.load(open('/tmp/acds_status.json')); print(f\"  kafka_connected={d.get('kafka_connected')} total_events={d.get('total_events')}\")"
else
    echo "  FAIL - backend not reachable on :8000"
fi

echo "[5] Kafka telemetry.raw (5s sample):"
COUNT=$(docker exec telemetry-kafka-1 kafka-console-consumer \
    --bootstrap-server localhost:9092 --topic telemetry.raw \
    --max-messages 1 --timeout-ms 5000 2>&1 | grep -c schema_version || true)
if [ "$COUNT" -gt 0 ]; then echo "  OK - events in Kafka"; else echo "  FAIL - 0 events (telemetry agent not publishing)"; fi

echo "[6] Traffic generator:"
pgrep -f generate_traffic.sh >/dev/null && echo "  OK - running" || echo "  NOT running - curl/ping won't create syscall events without agent anyway"

echo ""
echo "========== Fix checklist =========="
echo "  1. bash scripts/ensure_system_deps.sh   (if bcc failed)"
echo "  2. bash scripts/open_terminals.sh       (restart all tabs)"
echo "  3. In Telemetry tab: must see 'Agent active and polling'"
echo "  4. Open http://localhost:5173 and hard-refresh (Ctrl+Shift+R)"
