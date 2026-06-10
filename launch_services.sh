#!/usr/bin/env bash

# ACDS Full Stack Launcher (background mode — logs go to .service_logs/)
# For live logs in separate terminal tabs, use instead:
#   bash scripts/open_terminals.sh
#
# Run from WSL: bash launch_services.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}"
LOGS_DIR="${PROJECT_DIR}/.service_logs"

# shellcheck disable=SC1091
source "${PROJECT_DIR}/scripts/venv.sh"
TELEMETRY_PYTHONPATH="$(acds_telemetry_pythonpath)"

# Create logs directory
mkdir -p "${LOGS_DIR}"

if ! python3 -c "import bcc" 2>/dev/null; then
    echo "WARNING: python3-bpfcc not installed — Telemetry Agent will not capture events."
    echo "  Fix: bash scripts/ensure_system_deps.sh"
    echo ""
fi

echo "======================================"
echo "  ACDS Full Stack Launcher"
echo "======================================"
echo ""

# Check for sudo at the beginning so background tasks don't hang/fail
echo "✓ Authenticating sudo for required services..."
sudo -v

# Check if Docker containers are running
echo "✓ Checking Docker services..."
if ! docker exec telemetry-kafka-1 echo "ok" &>/dev/null; then
    echo "⚠️  WARNING: Kafka containers don't appear to be running."
    echo "    Run in another terminal: cd ${PROJECT_DIR}/acds/telemetry && docker compose up -d"
    read -p "    Press Enter to continue anyway, or Ctrl+C to abort..."
fi

echo ""
echo "✓ Starting ACDS services in background..."
echo ""

# Counter for services
SERVICES_STARTED=0

# =========== Telemetry Agent (requires sudo) ===========
echo "[1/9] Telemetry Agent (requires sudo)..."
if command -v sudo &> /dev/null; then
    # Try to run with sudo; if password needed it will prompt
    (cd "${PROJECT_DIR}/acds/telemetry/agent" && \
     sudo env PYTHONPATH="${TELEMETRY_PYTHONPATH}" "${ACDS_TELEMETRY_PY}" agent.py > "${LOGS_DIR}/telemetry_agent.log" 2>&1) &
    echo "  ↳ PID: $!"
    SERVICES_STARTED=$((SERVICES_STARTED + 1))
else
    echo "  ⚠️  Skipped (sudo not available)"
fi

# =========== DPI Service (requires sudo) ===========
echo "[2/9] DPI Service (requires sudo)..."
if command -v sudo &> /dev/null; then
    (cd "${PROJECT_DIR}" && \
     sudo env PYTHONPATH="${PROJECT_DIR}" "${ACDS_VENV_PY}" dpi_service/dpi_main.py > "${LOGS_DIR}/dpi_service.log" 2>&1) &
    echo "  ↳ PID: $!"
    SERVICES_STARTED=$((SERVICES_STARTED + 1))
else
    echo "  ⚠️  Skipped (sudo not available)"
fi

# =========== Correlation Service ===========
echo "[3/9] Correlation Service..."
(cd "${PROJECT_DIR}" && \
 "${ACDS_VENV_PY}" acds/correlation_service/correlation_main.py > "${LOGS_DIR}/correlation_service.log" 2>&1) &
echo "  ↳ PID: $!"
SERVICES_STARTED=$((SERVICES_STARTED + 1))

# =========== ML Detection Service ===========
echo "[4/9] ML Detection Service..."
(cd "${PROJECT_DIR}" && \
 "${ACDS_VENV_PY}" acds/ml_service/ml_main.py > "${LOGS_DIR}/ml_service.log" 2>&1) &
echo "  ↳ PID: $!"
SERVICES_STARTED=$((SERVICES_STARTED + 1))

# =========== LLM Triage Service (skipped — on-demand via UI button) ===========
echo "[5/9] LLM Triage Service (skipped — use UI 'Run AI Triage' per alert)..."

# =========== Graph Service ===========
echo "[6/9] Graph Service..."
(cd "${PROJECT_DIR}" && \
 "${ACDS_VENV_PY}" acds/graph_service/graph_main.py > "${LOGS_DIR}/graph_service.log" 2>&1) &
echo "  ↳ PID: $!"
SERVICES_STARTED=$((SERVICES_STARTED + 1))

# =========== Backend API ===========
echo "[7/9] Backend API (FastAPI)..."
(cd "${PROJECT_DIR}/acds/ui/backend" && \
 "${ACDS_VENV_PY}" -m uvicorn server:app --host 0.0.0.0 --port 8000 > "${LOGS_DIR}/backend_api.log" 2>&1) &
echo "  ↳ PID: $! - Running on http://localhost:8000"
SERVICES_STARTED=$((SERVICES_STARTED + 1))

# =========== React Frontend ===========
echo "[8/9] React Frontend (Vite)..."
(cd "${PROJECT_DIR}/acds/ui/frontend" && \
 npm run dev -- --host 0.0.0.0 --port 5173 > "${LOGS_DIR}/frontend.log" 2>&1) &
echo "  ↳ PID: $! - Running on http://localhost:5173"
SERVICES_STARTED=$((SERVICES_STARTED + 1))

# =========== Kafka Monitor ===========
echo "[9/9] Kafka Monitor (monitoring ml.alerts topic)..."
(cd "${PROJECT_DIR}" && \
 docker exec telemetry-kafka-1 kafka-console-consumer --bootstrap-server localhost:9092 --topic ml.alerts 2>/dev/null || \
 docker exec telemetry-kafka-1 kafka-console-consumer --bootstrap-server localhost:9092 --topic enriched.flows \
 > "${LOGS_DIR}/kafka_monitor.log" 2>&1) &
echo "  ↳ PID: $!"
SERVICES_STARTED=$((SERVICES_STARTED + 1))

# =========== Traffic Generator ===========
echo "[10/10] Traffic Generator (curl/ping for telemetry)..."
(cd "${PROJECT_DIR}" && \
 bash scripts/generate_traffic.sh > "${LOGS_DIR}/traffic_generator.log" 2>&1) &
echo "  ↳ PID: $!"

# =========== Demo Alert Injector (attack graph) ===========
echo "[+] Demo alerts (attack graph) — injecting after graph service is ready..."
(cd "${PROJECT_DIR}" && \
 bash scripts/inject_demo_after_startup.sh > "${LOGS_DIR}/demo_inject.log" 2>&1) &
echo "  ↳ PID: $! (see ${LOGS_DIR}/demo_inject.log)"

echo ""
echo "======================================"
echo "✅ Launched $SERVICES_STARTED services (+ traffic generator)!"
echo "======================================"
echo ""
echo "📊 Service Status:"
echo "  • Frontend UI:    http://localhost:5173"
echo "  • Backend API:    http://localhost:8000"
echo "  • Kafka UI:       http://localhost:8085"
echo "  • Neo4j:          http://localhost:7474 (login: neo4j / acds_password)"
echo "  • Ollama API:     http://localhost:11434"
echo ""
echo "📝 Logs:"
echo "  All service logs are in: ${LOGS_DIR}/"
echo "  View logs: tail -f ${LOGS_DIR}/<service>.log"
echo ""
echo "🛑 To stop all services: press Ctrl+C or run: pkill -f 'python3.*main.py'"
echo ""
echo "======================================"
echo ""

# Keep the script running so background jobs continue
wait
