# ACDS Services - Quick Reference

## 🚀 Services Status

Your ACDS stack is now running! Here's what's active:

### Running Services (in tmux session `acds`)

| # | Service | Port | Status | Notes |
|---|---------|------|--------|-------|
| 0 | Main Terminal | - | 🟢 | Control center |
| 1 | **Telemetry Agent** ⭐ | 9092 | ? | Requires sudo (eBPF kernel probes) |
| 2 | **DPI Service** ⭐ | 9092 | ? | Requires sudo (packet capture) |
| 3 | Correlation Service | 9092 | 🟢 | Enriches flows + risk scoring |
| 4 | ML Detection | 9092 | 🟢 | Ensemble anomaly detection |
| 5 | LLM Triage | 11434 | 🟢 | Local Ollama integration |
| 6 | Graph Service | 7687 | 🟢 | Neo4j attack graph |
| 7 | Backend API | **8000** | 🟢 | FastAPI REST/WebSocket bridge |
| 8 | Frontend UI | **5173** | 🟢 | React dashboard |
| 9 | Monitor | 9092 | 🟢 | Kafka topic consumer |

## 🔗 Access Points

- **Frontend Dashboard**: http://localhost:5173
- **Backend API**: http://localhost:8000 (API docs at /docs)
- **Neo4j Browser**: http://localhost:7474 (user: neo4j, pwd: acds_password)
- **Kafka UI**: http://localhost:8085
- **Ollama API**: http://localhost:11434

## 🪟 tmux Commands

```bash
# Attach to the running session
tmux attach -t acds

# See all windows
tmux list-windows -t acds

# Jump to specific window (example: window 7 for Backend)
tmux select-window -t acds:7
# Or press Ctrl+B then type :<number>

# Detach from session (while inside tmux)
# Press: Ctrl+B then D

# Kill the entire session
tmux kill-session -t acds
```

## 🟡 Important: Sudo Services (Windows 1 & 2)

**Telemetry Agent** and **DPI Service** require `sudo` for kernel access (eBPF) and packet capture.

If they're stuck waiting for password:
1. Press `Ctrl+B` then `:` to open tmux command mode
2. Type `send-keys -t acds:1 Enter` (for telemetry) or `send-keys -t acds:2 Enter` (for DPI)
3. This will send Enter to those windows
4. Or manually run:

```bash
# From your WSL terminal, run these separately:
sudo python3 /mnt/d/Desktop/Andrea/ACDS/acds/telemetry/agent/agent.py
sudo python3 /mnt/d/Desktop/Andrea/ACDS/dpi_service/dpi_main.py
```

## 📊 Data Flow

```
Kernel (eBPF) → Telemetry Agent → Kafka: telemetry.raw
                                    ↓
Network Packets → DPI Service ────→ Kafka: dpi.features
                                    ↓
                        Correlation Service (enriches)
                                    ↓
                           Kafka: enriched.flows
                                    ↓
                        ML Detection Service (scores)
                                    ↓
                           Kafka: ml.alerts
                                    ↓
                        Backend API (WebSocket bridge)
                                    ↓
                           React Frontend (visualize)
```

## 🧪 Generate Test Traffic

Once all services are running, open another WSL terminal and run:

```bash
cd /mnt/d/Desktop/Andrea/ACDS
bash scripts/generate_traffic.sh
```

This will create network events that flow through the entire pipeline.

## 📝 Logs & Debugging

Check service output in each tmux window. For persistent logs:

```bash
# Example: Monitor backend API in real-time
tmux capture-pane -t acds:7 -p

# Or switch to that window and follow output
tmux select-window -t acds:7
```

## 🛑 Stopping Services

- **All at once**: `tmux kill-session -t acds`
- **One at a time**: Go to window (Ctrl+B, :<num>) and press Ctrl+C

## ✅ Verification Checklist

- [ ] Docker containers running: `docker ps | grep telemetry`
- [ ] Kafka topics exist: `docker exec telemetry-kafka-1 kafka-topics --list --bootstrap-server localhost:9092`
- [ ] Neo4j accessible: Open http://localhost:7474
- [ ] Frontend loads: Open http://localhost:5173
- [ ] Backend responds: `curl http://localhost:8000/docs`
- [ ] Ollama available: `curl http://localhost:11434/api/tags`

## 🆘 Troubleshooting

**Services won't start?**
- Check Docker Compose is running: `docker ps`
- Verify ports aren't already in use: `lsof -i :8000` (change port as needed)

**Telemetry/DPI stuck?**
- These need sudo. Enter password when prompted, or run manually in separate terminal

**Kafka topics not visible?**
- Wait 30 seconds for services to initialize
- Check logs in respective tmux windows

**Can't connect to Ollama/Neo4j?**
- Ensure Docker containers are running
- Check: `docker exec telemetry-kafka-1 echo ok`
