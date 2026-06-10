#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}"

# shellcheck disable=SC1091
source "${PROJECT_DIR}/scripts/venv.sh"

WT="wt.exe"
PY="${ACDS_VENV_PY}"

"$WT" \
    new-tab --title "1_Telemetry_Agent_sudo" \
        wsl.exe bash -c "cd '$PROJECT_DIR/acds/telemetry/agent' && echo === TELEMETRY AGENT === && sudo env PYTHONPATH='$PROJECT_DIR' '$PY' agent.py; exec bash" \; \
    new-tab --title "2_DPI_Service_sudo" \
        wsl.exe bash -c "cd '$PROJECT_DIR' && echo === DPI SERVICE === && sudo env PYTHONPATH='$PROJECT_DIR' '$PY' dpi_service/dpi_main.py; exec bash" \; \
    new-tab --title "3_Correlation" \
        wsl.exe bash -c "cd '$PROJECT_DIR' && export PYTHONPATH='$PROJECT_DIR' && echo === CORRELATION === && '$PY' acds/correlation_service/correlation_main.py; exec bash" \; \
    new-tab --title "4_ML_Detection" \
        wsl.exe bash -c "cd '$PROJECT_DIR' && export PYTHONPATH='$PROJECT_DIR' && echo === ML DETECTION === && '$PY' acds/ml_service/ml_main.py; exec bash" \; \
    new-tab --title "5_LLM_Triage" \
        wsl.exe bash -c "cd '$PROJECT_DIR' && export PYTHONPATH='$PROJECT_DIR' && echo === LLM TRIAGE === && '$PY' acds/llm_service/llm_main.py; exec bash" \; \
    new-tab --title "6_Graph_Service" \
        wsl.exe bash -c "cd '$PROJECT_DIR' && export PYTHONPATH='$PROJECT_DIR' && echo === GRAPH SERVICE === && '$PY' acds/graph_service/graph_main.py; exec bash" \; \
    new-tab --title "7_Backend_API" \
        wsl.exe bash -c "cd '$PROJECT_DIR/acds/ui/backend' && export PYTHONPATH='$PROJECT_DIR' && echo === BACKEND API === && '$PY' -m uvicorn server:app --host 0.0.0.0 --port 8000; exec bash" \; \
    new-tab --title "8_Frontend_UI" \
        wsl.exe bash -c "cd '$PROJECT_DIR/acds/ui/frontend' && echo === FRONTEND UI === && npm run dev -- --host 0.0.0.0 --port 5173; exec bash" \; \
    new-tab --title "9_Kafka_Monitor" \
        wsl.exe bash -c "echo === KAFKA MONITOR === && sleep 3 && docker exec telemetry-kafka-1 kafka-console-consumer --bootstrap-server localhost:9092 --topic ml.alerts --from-beginning; exec bash" \; \
    new-tab --title "10_Traffic_Generator" \
        wsl.exe bash -c "cd '$PROJECT_DIR' && echo === TRAFFIC GENERATOR === && bash scripts/generate_traffic.sh; exec bash"
