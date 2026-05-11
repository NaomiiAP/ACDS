#!/usr/bin/env bash

# Hardcode the WSL-compatible path to avoid Git Bash vs WSL path mismatch
PROJECT_DIR="/mnt/d/Desktop/Andrea/ACDS"

WT="wt.exe"

"$WT" \
    new-tab --title "1_Telemetry_Agent_sudo" \
        wsl.exe bash -c "cd '$PROJECT_DIR/acds/telemetry/agent' && echo === TELEMETRY AGENT === && echo Requires sudo && echo && sudo python3 agent.py; bash" \; \
    \
    new-tab --title "2_DPI_Service_sudo" \
        wsl.exe bash -c "cd '$PROJECT_DIR' && echo === DPI SERVICE === && echo Requires sudo && echo && sudo python3 dpi_service/dpi_main.py; bash" \; \
    \
    new-tab --title "3_Correlation" \
        wsl.exe bash -c "cd '$PROJECT_DIR' && echo === CORRELATION === && python3 -m acds.correlation_service.correlation_main; bash" \; \
    \
    new-tab --title "4_ML_Detection" \
        wsl.exe bash -c "cd '$PROJECT_DIR' && echo === ML DETECTION === && python3 -m acds.ml_service.ml_main; bash" \; \
    \
    new-tab --title "5_LLM_Triage" \
        wsl.exe bash -c "cd '$PROJECT_DIR' && echo === LLM TRIAGE === && python3 -m acds.llm_service.llm_main; bash" \; \
    \
    new-tab --title "6_Graph_Service" \
        wsl.exe bash -c "cd '$PROJECT_DIR' && echo === GRAPH SERVICE === && python3 -m acds.graph_service.graph_main; bash" \; \
    \
    new-tab --title "7_Backend_API" \
        wsl.exe bash -c "cd '$PROJECT_DIR/acds/ui/backend' && echo === BACKEND API === && echo http://localhost:8000 && echo && python3 -m uvicorn server:app --host 0.0.0.0 --port 8000; bash" \; \
    \
    new-tab --title "8_Frontend_UI" \
        wsl.exe bash -c "cd '$PROJECT_DIR/acds/ui/frontend' && echo === FRONTEND UI === && echo http://localhost:5173 && echo && npm run dev -- --host 0.0.0.0 --port 5173; bash" \; \
    \
    new-tab --title "9_Kafka_Monitor" \
        wsl.exe bash -c "cd '$PROJECT_DIR' && echo === KAFKA MONITOR === && sleep 3 && docker exec telemetry-kafka-1 kafka-console-consumer --bootstrap-server localhost:9092 --topic ml.alerts --from-beginning 2>/dev/null; bash" \; \
    \
    new-tab --title "10_Traffic_Generator" \
        wsl.exe bash -c "cd '$PROJECT_DIR' && echo === TRAFFIC GENERATOR === && bash scripts/generate_traffic.sh; bash"
