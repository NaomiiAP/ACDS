#!/usr/bin/env bash

# IMPORTANT: Run this file from inside your WSL terminal!
# This script tells the Windows Terminal to open new tabs and pipes commands back into WSL.

WT="wt.exe"
PROJECT_DIR="/mnt/c/Users/PRANAV M K/MiniProject"
PASSWORD="Pmk190705*"

# Windows Terminal (`wt`) has a bug where it forcefully breaks commands on semicolons (;) even inside quotes. 
# We work around this by using `&& bash || bash` which guarantees the terminal drops to a functional 
# bash prompt whether you hit Ctrl+C (fail/130) or the command exits gracefully (success/0).

echo "Launching ACDS Telemetry Windows Terminal layout from WSL..."

"$WT" \
    new-tab --title "Telemetry Agent" wsl.exe bash -c "cd '${PROJECT_DIR}' && echo '${PASSWORD}' | sudo -S python3 acds/telemetry/agent/agent.py && bash || bash" \; \
    new-tab --title "Kafka CLI" wsl.exe bash -c "cd '${PROJECT_DIR}' && docker exec telemetry-kafka-1 kafka-console-consumer --bootstrap-server localhost:9092 --topic telemetry.raw --from-beginning && bash || bash" \; \
    new-tab --title "Python API Backend" wsl.exe bash -c "cd '${PROJECT_DIR}/acds/ui/backend' && python3 -m uvicorn server:app --host 0.0.0.0 --port 8000 && bash || bash" \; \
    new-tab --title "React UI Frontend" wsl.exe bash -c "cd '${PROJECT_DIR}/acds/ui/frontend' && npm run dev -- --host 0.0.0.0 --port 5173 && bash || bash" \; \
    new-tab --title "Network Generator" wsl.exe bash -c "cd '${PROJECT_DIR}' && ./scripts/generate_traffic.sh && bash || bash"