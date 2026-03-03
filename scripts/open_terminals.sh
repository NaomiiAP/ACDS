#!/usr/bin/env bash

# ACDS Full Stack Launcher
# Run from inside WSL: ./scripts/open_terminals.sh

WT="wt.exe"
PROJECT_DIR="/mnt/c/Users/PRANAV M K/MiniProject"
PASSWORD="Pmk190705*"

echo "Launching ACDS full stack in Windows Terminal..."

"$WT" \
    new-tab --title "🧠 Telemetry Agent" \
        wsl.exe bash -c "echo '${PASSWORD}' | sudo -S python3 '${PROJECT_DIR}/acds/telemetry/agent/agent.py' && bash || bash" \; \
    \
    new-tab --title "🌊 DPI Service" \
        wsl.exe bash -c "echo '${PASSWORD}' | sudo -S python3 '${PROJECT_DIR}/dpi_service/dpi_main.py' && bash || bash" \; \
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