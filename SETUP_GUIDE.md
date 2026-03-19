# ACDS Setup & Running Guide

## Complete instructions to set up and run the Autonomous Cyber Defense System

---

## Prerequisites

### Hardware Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 8 GB | 16 GB |
| Disk | 20 GB free | 40 GB free |
| CPU | 4 cores | 8 cores |
| GPU | Not required | NVIDIA (for CUDA-accelerated ML inference) |

### Software Requirements

| Software | Version | Purpose |
|----------|---------|---------|
| Windows | 10/11 (Build 19041+) | Host OS |
| WSL2 | Ubuntu 22.04 LTS | Linux kernel for eBPF |
| Docker Desktop | 4.x+ | Container infrastructure |
| Windows Terminal | Latest | Multi-tab service launcher |
| Python | 3.10+ | Backend services |
| Node.js | 18+ LTS | React frontend |
| npm | 9+ | Package management |
| Git | 2.x+ | Version control |

---

## Step 1: WSL2 Setup

### 1.1 Install WSL2 with Ubuntu

```powershell
# Run in PowerShell as Administrator
wsl --install -d Ubuntu-22.04
```

Restart your computer if prompted, then set up your Ubuntu username and password.

### 1.2 Install System Dependencies (inside WSL)

```bash
sudo apt update && sudo apt upgrade -y

# eBPF/BCC tools (required for telemetry agent)
sudo apt install -y bpfcc-tools python3-bpfcc linux-headers-$(uname -r)

# Python and pip
sudo apt install -y python3 python3-pip python3-venv

# Node.js 18 LTS
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Network tools (for DPI and traffic generation)
sudo apt install -y net-tools curl dnsutils iputils-ping
```

---

## Step 2: Docker Desktop Setup

### 2.1 Install Docker Desktop

1. Download Docker Desktop from https://www.docker.com/products/docker-desktop/
2. Install with WSL2 backend enabled
3. In Docker Desktop Settings:
   - General: Enable "Use the WSL 2 based engine"
   - Resources > WSL Integration: Enable integration with your Ubuntu distro

### 2.2 Verify Docker in WSL

```bash
docker --version
docker compose version
```

---

## Step 3: Clone the Repository

```bash
cd /mnt/d/Desktop/Andrea   # or your preferred directory
git clone https://github.com/praptirn/ACDS.git
cd ACDS
```

---

## Step 4: Install Python Dependencies

### 4.1 Core Dependencies (run from project root)

```bash
cd /mnt/d/Desktop/Andrea/ACDS

# Install all service requirements
pip3 install aiokafka confluent-kafka fastapi uvicorn websockets pydantic

# ML service dependencies
pip3 install numpy pandas scikit-learn xgboost imbalanced-learn torch onnxruntime joblib

# ONNX export tools
pip3 install onnxmltools skl2onnx onnxscript

# LLM service
pip3 install httpx

# Graph service
pip3 install neo4j

# DPI service
pip3 install scapy
```

### 4.2 Frontend Dependencies

```bash
cd acds/ui/frontend
npm install
cd ../../..
```

---

## Step 5: Start Docker Infrastructure

### 5.1 Start All Containers

```bash
cd acds/telemetry
docker compose up -d
```

This starts 5 containers:

| Container | Port | Health Check |
|-----------|------|-------------|
| Zookeeper | 2181 | `docker exec telemetry-zookeeper-1 echo ruok` |
| Kafka | 9092 | `docker exec telemetry-kafka-1 kafka-topics --bootstrap-server localhost:9092 --list` |
| Kafka UI | 8085 | Open http://localhost:8085 |
| Neo4j | 7474, 7687 | Open http://localhost:7474 (login: neo4j / acds_password) |
| Ollama | 11434 | `curl http://localhost:11434/api/tags` |

### 5.2 Wait for Services

```bash
# Wait ~15 seconds for all services to be healthy
sleep 15
docker compose ps
```

All containers should show status "Up".

### 5.3 Pull LLM Model

```bash
docker exec telemetry-ollama-1 ollama pull llama3.2
```

This downloads the Llama 3.2 model (~2 GB). Required for the LLM triage service.

---

## Step 6: Train ML Models

### 6.1 Download Datasets

Download the following datasets and place them in separate directories:

**CICIDS2017:**
- Download from: https://www.unb.ca/cic/datasets/ids-2017.html
- Files needed: All 8 CSV files (Monday through Friday)
- Place in: `D:/Downloads/cyberdataset/cicids2017/`

**UNSW-NB15:**
- Download from: https://research.unsw.edu.au/projects/unsw-nb15-dataset
- Files needed: UNSW-NB15_1.csv through UNSW-NB15_4.csv, training/testing sets
- Place in: `D:/Downloads/cyberdataset/unsw_nb15/`

### 6.2 Train Supervised Models (XGBoost + RandomForest)

```bash
cd /mnt/d/Desktop/Andrea/ACDS/acds

python3 -m ml_service.training.train_supervised \
    --cicids-dir "/mnt/d/Downloads/cyberdataset/cicids2017" \
    --unsw-dir "/mnt/d/Downloads/cyberdataset/unsw_nb15" \
    --output-dir "./ml_service/trained_models"
```

**Expected output:**
- 5-fold cross-validation with ~99.5% F1 scores
- Saves: `xgboost_model.joblib`, `random_forest_model.joblib`, `scaler.joblib`
- Duration: ~60-90 minutes (depending on hardware)

### 6.3 Train Unsupervised Models (Autoencoder + IsolationForest)

```bash
python3 -m ml_service.training.train_unsupervised \
    --cicids-dir "/mnt/d/Downloads/cyberdataset/cicids2017" \
    --unsw-dir "/mnt/d/Downloads/cyberdataset/unsw_nb15" \
    --output-dir "./ml_service/trained_models" \
    --ae-epochs 50
```

**Expected output:**
- Autoencoder: 50 epochs, loss converging ~0.262
- IsolationForest: Quick training (~1-2 minutes)
- Saves: `autoencoder_model.pt`, `isolation_forest_model.joblib`
- Duration: ~40 minutes

### 6.4 Export Models to ONNX

```bash
python3 -m ml_service.training.export_onnx \
    --model-dir "./ml_service/trained_models" \
    --output-dir "./ml_service/onnx_models"
```

**Expected output:**
- `xgboost.onnx` (2.1 MB)
- `random_forest.onnx` (11.9 MB)
- `autoencoder.onnx` (2.6 KB)
- `isolation_forest.onnx` (1.2 MB)

### 6.5 Verify Models

```bash
ls -la ml_service/trained_models/
ls -la ml_service/onnx_models/
```

You should see 5 files in `trained_models/` and 4 files in `onnx_models/`.

---

## Step 7: Launch the Full Stack

### Option A: Automated Launcher (Recommended)

The launcher script opens all services in separate Windows Terminal tabs:

```bash
cd /mnt/d/Desktop/Andrea/ACDS
chmod +x scripts/open_terminals.sh
bash scripts/open_terminals.sh
```

It will:
1. Prompt for your WSL sudo password
2. Restart Docker containers cleanly
3. Open 10 Windows Terminal tabs with all services

### Option B: Manual Launch (Service by Service)

Open separate terminals for each service. Start them in this order:

**Terminal 1 - Telemetry Agent (requires sudo):**
```bash
cd /mnt/d/Desktop/Andrea/ACDS
sudo python3 acds/telemetry/agent/agent.py
```

**Terminal 2 - DPI Service (requires sudo):**
```bash
cd /mnt/d/Desktop/Andrea/ACDS
sudo python3 dpi_service/dpi_main.py
```

**Terminal 3 - Correlation Service:**
```bash
cd /mnt/d/Desktop/Andrea/ACDS/acds/correlation_service
python3 correlation_main.py
```

**Terminal 4 - ML Detection Service:**
```bash
cd /mnt/d/Desktop/Andrea/ACDS/acds
python3 -m ml_service.ml_main
```

**Terminal 5 - LLM Triage Service:**
```bash
cd /mnt/d/Desktop/Andrea/ACDS/acds
python3 -m llm_service.llm_main
```

**Terminal 6 - Graph Service:**
```bash
cd /mnt/d/Desktop/Andrea/ACDS/acds
python3 -m graph_service.graph_main
```

**Terminal 7 - Backend API:**
```bash
cd /mnt/d/Desktop/Andrea/ACDS/acds/ui/backend
python3 -m uvicorn server:app --host 0.0.0.0 --port 8000
```

**Terminal 8 - React Frontend:**
```bash
cd /mnt/d/Desktop/Andrea/ACDS/acds/ui/frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

**Terminal 9 - Traffic Generator (for testing):**
```bash
cd /mnt/d/Desktop/Andrea/ACDS
chmod +x scripts/generate_traffic.sh
bash scripts/generate_traffic.sh
```

**Terminal 10 - Kafka Monitor (optional):**
```bash
docker exec telemetry-kafka-1 kafka-console-consumer \
    --bootstrap-server localhost:9092 \
    --topic ml.alerts
```

---

## Step 8: Access the Dashboard

Once all services are running, open your browser:

| URL | Service |
|-----|---------|
| http://localhost:5173 | ACDS React Dashboard |
| http://localhost:8085 | Kafka UI (topic browser) |
| http://localhost:7474 | Neo4j Browser (attack graph) |
| http://localhost:8000/api/status | Backend API health check |
| http://localhost:8000/docs | FastAPI auto-generated docs |

---

## Verification Checklist

After launching, verify each layer is working:

### Infrastructure
- [ ] `docker compose ps` shows 5 containers "Up"
- [ ] Kafka UI (http://localhost:8085) shows topics being created
- [ ] Neo4j browser (http://localhost:7474) is accessible

### Data Pipeline
- [ ] Telemetry agent shows "eBPF program loaded" and events flowing
- [ ] DPI service shows "Capturing packets on ..."
- [ ] Correlation service shows "Consumer started on telemetry.raw"
- [ ] Kafka UI shows messages in `telemetry.raw` and `enriched.flows` topics

### ML Pipeline
- [ ] ML service shows "Loaded models: ['xgboost', 'random_forest', 'autoencoder', 'isolation_forest']"
- [ ] ML service shows alerts being produced: `[HIGH] ensemble=0.82 ...`
- [ ] Kafka UI shows messages in `ml.alerts` topic

### LLM + Graph
- [ ] LLM service shows "Triage consumer started" and triage results
- [ ] Graph service shows "Neo4j connected" and graph updates
- [ ] Neo4j browser shows nodes appearing (run: `MATCH (n) RETURN n LIMIT 25`)

### Frontend
- [ ] Dashboard loads at http://localhost:5173
- [ ] Live Stream page shows real-time events
- [ ] Threats page shows enriched flows with risk scores
- [ ] ML Detection page shows alerts (if traffic generator is running)

---

## Troubleshooting

### Docker Issues

**"Cannot connect to the Docker daemon"**
```bash
# Make sure Docker Desktop is running on Windows
# Then in WSL:
docker ps
```

**Containers keep restarting:**
```bash
docker compose logs kafka    # Check Kafka logs
docker compose down && docker compose up -d   # Full restart
```

### Kafka Issues

**"NoBrokersAvailable" error:**
```bash
# Kafka may not be fully started yet. Wait 15-20 seconds after docker compose up.
# Verify Kafka is listening:
docker exec telemetry-kafka-1 kafka-topics --bootstrap-server localhost:9092 --list
```

### ML Service Issues

**"ONNX model not found":**
```bash
# Make sure you ran the export step:
ls acds/ml_service/onnx_models/
# Should show: xgboost.onnx, random_forest.onnx, autoencoder.onnx, isolation_forest.onnx
```

**"ModuleNotFoundError":**
```bash
# Install missing packages:
pip3 install <package_name>
# Or install all at once:
pip3 install -r acds/ml_service/requirements.txt
```

### Telemetry Agent Issues

**"Permission denied" or "BPF not available":**
```bash
# Must run with sudo:
sudo python3 acds/telemetry/agent/agent.py

# If kernel headers are missing:
sudo apt install -y linux-headers-$(uname -r)
```

### Neo4j Issues

**"ServiceUnavailable" error:**
```bash
# Check Neo4j container:
docker logs telemetry-neo4j-1
# Default credentials: neo4j / acds_password
```

### Ollama Issues

**"Model not found":**
```bash
# Pull the model first:
docker exec telemetry-ollama-1 ollama pull llama3.2

# Verify:
docker exec telemetry-ollama-1 ollama list
```

### Frontend Issues

**"npm run dev" fails:**
```bash
cd acds/ui/frontend
rm -rf node_modules package-lock.json
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

---

## Stopping the Stack

### Stop All Services
```bash
# If using the launcher, close all Windows Terminal tabs, then:
cd /mnt/d/Desktop/Andrea/ACDS/acds/telemetry
docker compose down
```

### Stop Only Docker Containers (keep services running)
```bash
docker compose stop
```

### Full Cleanup (removes volumes)
```bash
docker compose down -v
```

---

## Project Directory Structure

```
ACDS/
├── acds/
│   ├── telemetry/
│   │   ├── agent/
│   │   │   ├── agent.py              # eBPF telemetry agent
│   │   │   ├── kafka_producer.py      # Kafka producer wrapper
│   │   │   ├── container_mapper.py    # Container ID resolution
│   │   │   └── config.py             # Agent configuration
│   │   ├── ebpf/
│   │   │   └── telemetry.c           # eBPF kernel program
│   │   └── docker-compose.yml        # Kafka, Neo4j, Ollama
│   │
│   ├── correlation_service/
│   │   ├── correlation_main.py        # Flow correlation entry point
│   │   ├── flow_correlator.py         # Process-to-network correlation
│   │   ├── risk_scorer.py             # Initial risk scoring
│   │   └── state_store.py            # Active connection registry
│   │
│   ├── ml_service/
│   │   ├── ml_main.py                # ML detection entry point
│   │   ├── api.py                    # REST API for manual scoring
│   │   ├── feature_pipeline.py        # Sliding window features
│   │   ├── models/
│   │   │   ├── supervised.py          # XGBoost + RandomForest
│   │   │   ├── unsupervised.py        # Autoencoder + IsolationForest
│   │   │   └── ensemble.py           # Weighted ensemble
│   │   ├── inference/
│   │   │   ├── onnx_runner.py         # ONNX Runtime inference
│   │   │   └── threshold_manager.py   # Dynamic thresholding
│   │   ├── training/
│   │   │   ├── dataset_loader.py      # CICIDS2017 + UNSW-NB15 loader
│   │   │   ├── train_supervised.py    # Supervised training script
│   │   │   ├── train_unsupervised.py  # Unsupervised training script
│   │   │   ├── export_onnx.py         # ONNX export script
│   │   │   └── evaluate.py           # Model evaluation
│   │   ├── registry/
│   │   │   └── model_registry.py      # Model version management
│   │   ├── trained_models/            # .joblib + .pt files (not in git)
│   │   └── onnx_models/              # .onnx files (not in git)
│   │
│   ├── llm_service/
│   │   ├── llm_main.py               # LLM triage entry point
│   │   ├── ollama_client.py           # Async Ollama HTTP client
│   │   ├── prompt_templates.py        # Structured triage prompts
│   │   └── triage_formatter.py        # LLM output parser
│   │
│   ├── graph_service/
│   │   ├── graph_main.py             # Graph service entry point
│   │   ├── neo4j_client.py           # Async Neo4j driver
│   │   ├── graph_schema.py           # Cypher query builders
│   │   ├── risk_propagation.py        # Time-decayed risk propagation
│   │   ├── path_ranker.py            # Attack path ranking
│   │   └── api.py                    # REST API for graph queries
│   │
│   └── ui/
│       ├── backend/
│       │   └── server.py             # FastAPI backend + WebSocket
│       └── frontend/
│           ├── src/
│           │   ├── App.jsx            # Main app with routing
│           │   ├── pages/
│           │   │   ├── Dashboard.jsx   # Overview dashboard
│           │   │   ├── LiveStream.jsx  # Real-time events
│           │   │   ├── Threats.jsx     # Threat visualization
│           │   │   ├── MLDetection.jsx # ML alert browser
│           │   │   └── AttackGraph.jsx # Neo4j graph viz
│           │   ├── hooks/
│           │   │   ├── useTelemetry.js # WebSocket hook
│           │   │   └── useMLAlerts.js  # ML alert hook
│           │   └── context/
│           │       ├── TelemetryContext.jsx
│           │       └── SettingsContext.jsx
│           ├── package.json
│           └── vite.config.js
│
├── dpi_service/
│   ├── dpi_main.py                    # DPI entry point
│   ├── packet_capture.py              # Scapy packet capture
│   ├── flow_manager.py                # Bidirectional flow tracking
│   ├── feature_extractor.py           # Statistical feature extraction
│   └── kafka_publisher.py             # Kafka producer
│
├── scripts/
│   ├── open_terminals.sh              # Full stack launcher
│   ├── generate_traffic.sh            # Synthetic traffic generator
│   └── wsl_setup.sh                  # WSL dependency installer
│
├── PROJECT_REPORT.md                  # Detailed project explanation
├── SETUP_GUIDE.md                     # This file
└── README.md                          # Project overview
```
