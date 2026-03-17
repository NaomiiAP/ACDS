#!/usr/bin/env bash

# ACDS Full Stack Launcher
# Run from inside WSL: ./scripts/open_terminals.sh

WT="wt.exe"

# Resolve project root relative to this script's location (scripts/../)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
KAFKA_DIR="${PROJECT_DIR}/acds/telemetry"

# Read sudo password securely at runtime — never hardcode credentials
read -rsp "[ACDS] Enter your WSL sudo password: " PASSWORD
echo ""

# ── Step 1: Restart Kafka + Zookeeper cleanly ─────────────────────────────────
echo "============================================="
echo "  ACDS: Restarting Kafka stack (clean)..."
echo "============================================="

cd "${KAFKA_DIR}" || { echo "ERROR: Cannot find telemetry dir at ${KAFKA_DIR}"; exit 1; }

echo "[1/3] Stopping existing containers..."
docker compose down

echo "[2/3] Starting Kafka, Zookeeper, Kafka-UI..."
docker compose up -d

echo "[3/3] Waiting for services to become healthy..."
sleep 15

echo ""
echo "--- Docker Compose Status ---"
docker compose ps
echo "-----------------------------"
echo ""

# Verify all required services are running
RUNNING=$(docker compose ps --services --filter "status=running" 2>/dev/null | wc -l)
if [ "${RUNNING}" -lt 3 ]; then
    echo "⚠️  WARNING: Not all Kafka services appear to be running."
    echo "    Check output above. You may need to restart Docker Desktop."
    echo "    Press Enter to continue anyway, or Ctrl+C to abort."
    read -r
else
    echo "✅ All Kafka services are running. Launching ACDS terminals..."
fi

echo ""
echo "Launching ACDS full stack in Windows Terminal..."

"$WT" \
    new-tab --title "🧠 Telemetry Agent" \
        wsl.exe bash -c "echo '${PASSWORD}' | sudo -S python3 '${PROJECT_DIR}/acds/telemetry/agent/agent.py' 2>&1 && bash || bash" \; \
    \
    new-tab --title "🌊 DPI Service" \
        wsl.exe bash -c "echo '${PASSWORD}' | sudo -S python3 '${PROJECT_DIR}/dpi_service/dpi_main.py' 2>&1 && bash || bash" \; \
    \
    new-tab --title "🔗 Correlation Service" \
        wsl.exe bash -c "cd '${PROJECT_DIR}/acds/correlation_service' && python3 correlation_main.py && bash || bash" \; \
    \
    new-tab --title "⚡ Python API Backend" \
        wsl.exe bash -c "cd '${PROJECT_DIR}/acds/ui/backend' && python3 -m uvicorn server:app --host 0.0.0.0 --port 8000 && bash || bash" \; \
    \
    new-tab --title "🌐 React UI Frontend" \
        wsl.exe bash -c "cd '${PROJECT_DIR}/acds/ui/frontend' && npm run dev -- --host 0.0.0.0 --port 5173 && bash || bash" \; \
    \
    new-tab --title "📨 Kafka Monitor" \
        wsl.exe bash -c "docker exec telemetry-kafka-1 kafka-console-consumer --bootstrap-server localhost:9092 --topic enriched.flows 2>/dev/null || docker exec telemetry-kafka-1 kafka-console-consumer --bootstrap-server localhost:9092 --topic telemetry.raw && bash || bash" \; \
    \
    new-tab --title "🔁 Traffic Generator" \
        wsl.exe bash -c "cd '${PROJECT_DIR}' && ./scripts/generate_traffic.sh && bash || bash"