#!/usr/bin/env bash

# ACDS Full Stack Launcher with tmux
# Run from WSL: bash launch_with_tmux.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}"
SESSION_NAME="acds"
LOGS_DIR="${PROJECT_DIR}/.service_logs"

mkdir -p "${LOGS_DIR}"

echo "======================================"
echo "  ACDS Stack Launcher (tmux)"
echo "======================================"
echo ""

# Kill any existing tmux session
tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true
sleep 1

# Create new tmux session with first window
tmux new-session -d -s "$SESSION_NAME" -x 180 -y 50 -c "$PROJECT_DIR"

echo "✓ Creating tmux session: $SESSION_NAME"
echo ""

# Window 1: Telemetry Agent
echo "[1/9] Creating window: Telemetry Agent (sudo required)"
tmux new-window -t "$SESSION_NAME" -n "telemetry"
tmux send-keys -t "$SESSION_NAME:telemetry" "cd $PROJECT_DIR/acds/telemetry/agent && echo 'Starting Telemetry Agent (sudo)...' && sudo python3 agent.py" Enter
sleep 2

# Window 2: DPI Service
echo "[2/9] Creating window: DPI Service (sudo required)"
tmux new-window -t "$SESSION_NAME" -n "dpi"
tmux send-keys -t "$SESSION_NAME:dpi" "cd $PROJECT_DIR && echo 'Starting DPI Service (sudo)...' && sudo python3 dpi_service/dpi_main.py" Enter
sleep 2

# Window 3: Correlation Service
echo "[3/9] Creating window: Correlation Service"
tmux new-window -t "$SESSION_NAME" -n "correlation"
tmux send-keys -t "$SESSION_NAME:correlation" "cd $PROJECT_DIR/acds/correlation_service && python3 correlation_main.py" Enter
sleep 1

# Window 4: ML Detection
echo "[4/9] Creating window: ML Detection"
tmux new-window -t "$SESSION_NAME" -n "ml"
tmux send-keys -t "$SESSION_NAME:ml" "cd $PROJECT_DIR/acds/ml_service && python3 ml_main.py" Enter
sleep 1

# Window 5: LLM Triage
echo "[5/9] Creating window: LLM Triage"
tmux new-window -t "$SESSION_NAME" -n "llm"
tmux send-keys -t "$SESSION_NAME:llm" "cd $PROJECT_DIR/acds/llm_service && python3 llm_main.py" Enter
sleep 1

# Window 6: Graph Service
echo "[6/9] Creating window: Graph Service"
tmux new-window -t "$SESSION_NAME" -n "graph"
tmux send-keys -t "$SESSION_NAME:graph" "cd $PROJECT_DIR/acds/graph_service && python3 graph_main.py" Enter
sleep 1

# Window 7: Backend API
echo "[7/9] Creating window: Backend API (FastAPI)"
tmux new-window -t "$SESSION_NAME" -n "backend"
tmux send-keys -t "$SESSION_NAME:backend" "cd $PROJECT_DIR/acds/ui/backend && python3 -m uvicorn server:app --host 0.0.0.0 --port 8000" Enter
sleep 1

# Window 8: Frontend
echo "[8/9] Creating window: Frontend (React/Vite)"
tmux new-window -t "$SESSION_NAME" -n "frontend"
tmux send-keys -t "$SESSION_NAME:frontend" "cd $PROJECT_DIR/acds/ui/frontend && npm run dev -- --host 0.0.0.0 --port 5173" Enter
sleep 1

# Window 9: Kafka Monitor
echo "[9/9] Creating window: Kafka Monitor"
tmux new-window -t "$SESSION_NAME" -n "monitor"
tmux send-keys -t "$SESSION_NAME:monitor" "echo 'Waiting for Kafka services...' && sleep 5 && docker exec telemetry-kafka-1 kafka-console-consumer --bootstrap-server localhost:9092 --topic ml.alerts --from-beginning 2>/dev/null || docker exec telemetry-kafka-1 kafka-console-consumer --bootstrap-server localhost:9092 --topic enriched.flows" Enter

# Select Window 0 (Main)
tmux select-window -t "$SESSION_NAME:0"

echo ""
echo "======================================"
echo "✅ ACDS Stack Launched!"
echo "======================================"
echo ""
echo "📊 Service Status:"
echo "  • Frontend UI:    http://localhost:5173"
echo "  • Backend API:    http://localhost:8000"
echo "  • Kafka UI:       http://localhost:8085"
echo "  • Neo4j:          http://localhost:7474"
echo "  • Ollama API:     http://localhost:11434"
echo ""
echo "🪟 tmux Commands:"
echo "  • List windows:     tmux list-windows -t $SESSION_NAME"
echo "  • Jump to window:   tmux select-window -t $SESSION_NAME:<num>"
echo "  • Attach to session: tmux attach -t $SESSION_NAME"
echo "  • Kill all:         tmux kill-session -t $SESSION_NAME"
echo ""
echo "⚠️  IMPORTANT: Windows 1-2 (Telemetry & DPI) need sudo and may prompt for password"
echo "    If stuck, press Enter or Ctrl+C and run those manually with sudo"
echo ""
echo "📝 Service Windows:"
echo "  0: Main            7: Backend API"
echo "  1: Telemetry ⭐    8: Frontend"
echo "  2: DPI ⭐          9: Monitor"
echo "  3: Correlation   "
echo "  4: ML Detection   "
echo "  5: LLM Triage     "
echo "  6: Graph Service  "
echo ""

# Attach to session
echo "Attaching to tmux session... (Ctrl+B then D to detach)"
tmux attach -t "$SESSION_NAME"
