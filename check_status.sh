#!/usr/bin/env bash

# ACDS Services Status Checker

echo "======================================"
echo "  ACDS Services Status Check"
echo "======================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check tmux session
echo "🪟 tmux Session:"
if tmux list-sessions -F '#{session_name}' 2>/dev/null | grep -q '^acds$'; then
    echo -e "  ${GREEN}✓${NC} Session 'acds' is running"
    echo "  Windows:"
    tmux list-windows -t acds -F '#{window_index}: #{window_name}' 2>/dev/null | sed 's/^/    /'
else
    echo -e "  ${RED}✗${NC} Session 'acds' is NOT running"
    echo "    Start it with: bash launch_with_tmux.sh"
fi

echo ""
echo "🔗 Service Port Checks:"

# Check Backend API
echo -n "  Backend API (8000): "
if curl -s http://localhost:8000/docs > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not responding${NC}"
fi

# Check Frontend
echo -n "  Frontend (5173): "
if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not responding${NC}"
fi

# Check Kafka
echo -n "  Kafka (9092): "
if docker exec telemetry-kafka-1 echo ok 2>/dev/null >/dev/null; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not responding${NC}"
fi

# Check Neo4j
echo -n "  Neo4j (7687): "
if curl -s -u neo4j:acds_password http://localhost:7474/db/neo4j/summary > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not responding${NC}"
fi

# Check Ollama
echo -n "  Ollama (11434): "
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not responding${NC}"
fi

echo ""
echo "📊 Python Services (process check):"

# Check for running Python services
for service in "correlation_main.py" "ml_main.py" "llm_main.py" "graph_main.py" "agent.py" "dpi_main.py"; do
    echo -n "  $service: "
    if pgrep -f "$service" > /dev/null; then
        count=$(pgrep -f "$service" | wc -l)
        echo -e "${GREEN}✓ Running${NC} ($count process)"
    else
        echo -e "${RED}✗ Not found${NC}"
    fi
done

echo ""
echo "📨 Kafka Topics:"
docker exec telemetry-kafka-1 kafka-topics --list --bootstrap-server localhost:9092 2>/dev/null | sed 's/^/  /'

echo ""
echo "======================================"
echo ""
echo "💡 To see service details:"
echo "   tmux select-window -t acds:<number>"
echo ""
echo "📖 For detailed instructions, see: RUNNING.md"
echo ""
