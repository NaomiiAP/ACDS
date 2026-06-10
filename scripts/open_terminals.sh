#!/usr/bin/env bash

# ACDS Full Stack Launcher — opens each service in its own Windows Terminal tab
# Run from WSL (repo root): bash scripts/open_terminals.sh

WT="wt.exe"
if ! command -v "$WT" &>/dev/null; then
    echo "ERROR: Windows Terminal (wt.exe) not found."
    echo "Install Windows Terminal, or use: bash launch_with_tmux.sh"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
KAFKA_DIR="${PROJECT_DIR}/acds/telemetry"

# shellcheck disable=SC1091
source "${SCRIPT_DIR}/venv.sh"
VENV_PY="${ACDS_VENV_PY}"
TELEMETRY_PY="${ACDS_TELEMETRY_PY}"
TELEMETRY_PYTHONPATH="$(acds_telemetry_pythonpath)"

echo "============================================="
echo "  ACDS: Launching services in terminal tabs"
echo "============================================="
echo "Project: ${PROJECT_DIR}"
echo ""

# ── Kafka / Docker ─────────────────────────────────────────────────────────────
cd "${KAFKA_DIR}" || { echo "ERROR: Cannot find ${KAFKA_DIR}"; exit 1; }

if docker exec telemetry-kafka-1 echo ok &>/dev/null; then
    echo "✓ Kafka stack already running"
else
    echo "Starting Kafka, Zookeeper, Neo4j, Ollama..."
    docker compose up -d
    echo "Waiting for services to become healthy..."
    sleep 15
    docker compose ps
fi

echo ""
read -rsp "[ACDS] Enter your WSL sudo password (for Telemetry + DPI tabs): " PASSWORD
echo ""

# Cache sudo credentials for the session
echo "${PASSWORD}" | sudo -S -v >/dev/null 2>&1 || {
    echo "ERROR: sudo authentication failed"
    exit 1
}

# Auto-install system packages for Telemetry (bcc) and DPI (libpcap)
if ! python3 -c "import bcc" 2>/dev/null || ! ldconfig -p 2>/dev/null | grep -q libpcap.so; then
    echo "Installing system packages (bpfcc-tools, python3-bpfcc, libpcap-dev)..."
    echo "${PASSWORD}" | sudo -S apt-get update -qq
    echo "${PASSWORD}" | sudo -S apt-get install -y bpfcc-tools python3-bpfcc libpcap-dev
    echo "${PASSWORD}" | sudo -S apt-get install -y "linux-headers-$(uname -r)" 2>/dev/null || \
        echo "${PASSWORD}" | sudo -S apt-get install -y linux-headers-generic 2>/dev/null || true
    if python3 -c "import bcc" 2>/dev/null; then
        echo "✓ bcc installed"
    else
        echo "ERROR: bcc still not available after install. Try: bash scripts/ensure_system_deps.sh"
        exit 1
    fi
fi

if ! bash "${SCRIPT_DIR}/test_telemetry_imports.sh" >/dev/null 2>&1; then
    echo "ERROR: Telemetry agent dependencies broken. Run: bash scripts/install_deps.sh"
    bash "${SCRIPT_DIR}/test_telemetry_imports.sh"
    exit 1
fi
echo "✓ Telemetry agent dependencies OK"

echo ""
echo "Opening Windows Terminal tabs (logs stream live in each tab)..."
echo ""

# First tab replaces the current wt window; rest are new-tab
"$WT" \
    new-tab --title "Telemetry Agent" \
        wsl.exe bash -lc "cd '${PROJECT_DIR}/acds/telemetry/agent' && echo '=== TELEMETRY AGENT ===' && echo '${PASSWORD}' | sudo -S env PYTHONPATH='${TELEMETRY_PYTHONPATH}' '${TELEMETRY_PY}' agent.py; exec bash" \; \
    new-tab --title "DPI Service" \
        wsl.exe bash -lc "cd '${PROJECT_DIR}' && echo '=== DPI SERVICE ===' && echo '${PASSWORD}' | sudo -S env PYTHONPATH='${PROJECT_DIR}' '${VENV_PY}' dpi_service/dpi_main.py; exec bash" \; \
    new-tab --title "Correlation" \
        wsl.exe bash -lc "cd '${PROJECT_DIR}' && export PYTHONPATH='${PROJECT_DIR}' && echo '=== CORRELATION SERVICE ===' && '${VENV_PY}' acds/correlation_service/correlation_main.py; exec bash" \; \
    new-tab --title "ML Detection" \
        wsl.exe bash -lc "cd '${PROJECT_DIR}' && export PYTHONPATH='${PROJECT_DIR}' && echo '=== ML DETECTION ===' && '${VENV_PY}' acds/ml_service/ml_main.py; exec bash" \; \
    new-tab --title "Policy Engine" \
        wsl.exe bash -lc "cd '${PROJECT_DIR}' && export PYTHONPATH='${PROJECT_DIR}' && echo '=== POLICY ENGINE ===' && '${VENV_PY}' acds/policy_service/policy_main.py; exec bash" \; \
    new-tab --title "Graph Service" \
        wsl.exe bash -lc "cd '${PROJECT_DIR}' && export PYTHONPATH='${PROJECT_DIR}' && echo '=== GRAPH SERVICE ===' && '${VENV_PY}' acds/graph_service/graph_main.py; exec bash" \; \
    new-tab --title "Demo Alerts" \
        wsl.exe bash -lc "cd '${PROJECT_DIR}' && echo '=== DEMO ALERT INJECTOR ===' && bash scripts/inject_demo_after_startup.sh; exec bash" \; \
    new-tab --title "Backend API" \
        wsl.exe bash -lc "cd '${PROJECT_DIR}/acds/ui/backend' && export PYTHONPATH='${PROJECT_DIR}' && echo '=== BACKEND API ===' && echo 'http://localhost:8000' && '${VENV_PY}' -m uvicorn server:app --host 0.0.0.0 --port 8000; exec bash" \; \
    new-tab --title "Frontend UI" \
        wsl.exe bash -lc "echo '=== FRONTEND UI ===' && echo 'http://localhost:5173' && bash '${PROJECT_DIR}/scripts/start_frontend.sh'; exec bash" \; \
    new-tab --title "Kafka Monitor" \
        wsl.exe bash -lc "echo '=== KAFKA MONITOR (ml.alerts) ===' && sleep 2 && docker exec telemetry-kafka-1 kafka-console-consumer --bootstrap-server localhost:9092 --topic ml.alerts --from-beginning; exec bash" \; \
    new-tab --title "LLM Triage" \
        wsl.exe bash -lc "echo '=== LLM TRIAGE (on-demand) ===' && echo 'Skipped at startup. Use the Run AI Triage button in the ML Detection UI.' && echo 'Or run manually: cd ${PROJECT_DIR} && ${VENV_PY} acds/llm_service/llm_main.py' && exec bash" \; \
    new-tab --title "Traffic Generator" \
        wsl.exe bash -lc "cd '${PROJECT_DIR}' && echo '=== TRAFFIC GENERATOR ===' && bash scripts/generate_traffic.sh; exec bash"

echo ""
echo "✅ Terminal tabs launched!"
echo ""
echo "  Frontend UI:  http://localhost:5173"
echo "  Backend API:  http://localhost:8000"
echo "  Kafka UI:     http://localhost:8085"
echo "  Neo4j:        http://localhost:7474  (neo4j / acds_password)"
echo ""
