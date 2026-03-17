# ACDS — Adaptive Cyber Detection System

> **A real-time network telemetry, deep-packet-inspection, and threat-detection platform running on Linux (WSL2) with a React dashboard.**

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture & Data Flow](#2-architecture--data-flow)
3. [Prerequisites](#3-prerequisites)
4. [Repository Structure](#4-repository-structure)
5. [Installation](#5-installation)
   - [5.1 System Packages (WSL2/Ubuntu)](#51-system-packages-wsl2--ubuntu)
   - [5.2 Docker Desktop (Windows)](#52-docker-desktop-windows)
   - [5.3 Python Virtual Environments](#53-python-virtual-environments)
   - [5.4 Node.js & Frontend Dependencies](#54-nodejs--frontend-dependencies)
6. [One-Time Configuration](#6-one-time-configuration)
7. [Running the Full Stack](#7-running-the-full-stack)
   - [7.1 Using `open_terminals.sh` (Recommended)](#71-using-open_terminalssh-recommended)
   - [7.2 Manual Step-by-Step](#72-manual-step-by-step)
8. [Generating Test Traffic](#8-generating-test-traffic)
9. [Accessing the UI & Services](#9-accessing-the-ui--services)
10. [Stopping the Stack](#10-stopping-the-stack)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Project Overview

ACDS is a five-layer security observability pipeline:

| Layer | Service | Role |
|-------|---------|------|
| **L4** | **Telemetry Agent** (`acds/telemetry/agent/`) | eBPF kernel probes capture every `connect` and `execve` syscall and publish raw events to Kafka (`telemetry.raw`) |
| **L5** | **DPI Service** (`dpi_service/`) | Scapy packet capture builds bidirectional flows and extracts statistical features, publishing to Kafka (`dpi.features`) |
| **L6** | **Correlation Service** (`acds/correlation_service/`) | Consumes both Kafka topics, correlates process identity with network flows, scores risk, and publishes fully attributed events (`enriched.flows`) |
| **L7** | **Backend API** (`acds/ui/backend/`) | FastAPI server bridges Kafka to the browser via REST endpoints and WebSockets (`/ws/telemetry`, `/ws/threats`) |
| **UI** | **React Frontend** (`acds/ui/frontend/`) | Vite + React dashboard visualising live telemetry events, DPI flows, and threat scores in real time |

Kafka (with Zookeeper) runs inside Docker and connects all layers together.

---

## 2. Architecture & Data Flow

```
┌─────────────────────────────────────────────────────┐
│                    Linux Kernel                     │
│   syscall: connect / execve                         │
│          │  (eBPF kprobe)                           │
│          ▼                                          │
│   Telemetry Agent ──────────► Kafka: telemetry.raw  │
│                                        │            │
│   Network Interface                    │            │
│          │  (Scapy capture)            │            │
│          ▼                             │            │
│   DPI Service ──────────────► Kafka: dpi.features   │
│                                        │            │
│                               Correlation Service   │
│                           (correlate + risk score)  │
│                                        │            │
│                               Kafka: enriched.flows │
│                                        │            │
│                               FastAPI Backend API   │
│                          (REST + WebSocket bridge)  │
│                                        │            │
│                               React UI Dashboard    │
└─────────────────────────────────────────────────────┘
```

**Kafka Topics:**

| Topic | Producer | Consumer |
|-------|----------|----------|
| `telemetry.raw` | Telemetry Agent | Correlation Service, Backend API |
| `dpi.features` | DPI Service | Correlation Service |
| `enriched.flows` | Correlation Service | Backend API |

---

## 3. Prerequisites

### Windows Host
| Requirement | Version | Notes |
|-------------|---------|-------|
| **Windows 10/11** | Build 19041+ | WSL2 support |
| **WSL2** | — | Ubuntu 22.04 LTS recommended |
| **Windows Terminal** | Latest | Required by `open_terminals.sh` to launch tabs |
| **Docker Desktop** | 4.x+ | Must have WSL2 backend enabled |

### Inside WSL2 (Ubuntu)
| Requirement | Version | Notes |
|-------------|---------|-------|
| **Linux Kernel** | ≥ 5.8 | Required for eBPF / BCC |
| **Python 3** | ≥ 3.10 | `python3`, `pip3` |
| **Node.js** | ≥ 18 LTS | For the React frontend |
| **npm** | ≥ 9 | Bundled with Node.js |
| **bpfcc-tools** | Latest | eBPF tooling (apt package) |
| **python3-bpfcc** | Latest | Python BCC bindings (apt package) |
| **curl** | Any | Used by `generate_traffic.sh` |
| **iputils-ping** | Any | Used by `generate_traffic.sh` |
| **dnsutils** | Any | `nslookup` in `generate_traffic.sh` |

---

## 4. Repository Structure

```
MiniProject/
├── scripts/
│   ├── open_terminals.sh      # ← Main launcher: starts Docker + all 6 services in Windows Terminal tabs
│   └── generate_traffic.sh   # ← Continuous traffic generator for testing
│
├── acds/
│   ├── telemetry/
│   │   ├── agent/             # eBPF Telemetry Agent (Python + BCC)
│   │   │   ├── agent.py       # Entry point (requires root)
│   │   │   ├── kafka_producer.py
│   │   │   ├── container_mapper.py
│   │   │   └── config.py
│   │   ├── ebpf/
│   │   │   └── telemetry.c    # eBPF C program (compiled at runtime by BCC)
│   │   ├── docker-compose.yml # Zookeeper + Kafka + Kafka-UI
│   │   └── requirements.txt
│   │
│   ├── correlation_service/   # Layer 6: Correlator + Risk Scorer
│   │   ├── correlation_main.py
│   │   ├── flow_correlator.py
│   │   ├── risk_scorer.py
│   │   ├── state_store.py
│   │   └── requirements.txt
│   │
│   └── ui/
│       ├── backend/           # FastAPI WebSocket bridge
│       │   ├── server.py
│       │   └── requirements.txt
│       └── frontend/          # React + Vite dashboard
│           ├── src/
│           ├── package.json
│           └── vite.config.js
│
└── dpi_service/               # Layer 5: Deep Packet Inspection
    ├── dpi_main.py
    ├── packet_capture.py
    ├── flow_manager.py
    ├── feature_extractor.py
    ├── kafka_publisher.py
    └── requirements.txt
```

---

## 5. Installation

All installation commands below are run **inside a WSL2 terminal** unless stated otherwise.

### 5.1 System Packages (WSL2 / Ubuntu)

```bash
sudo apt update && sudo apt upgrade -y

# Core system tools
sudo apt install -y python3 python3-pip python3-venv \
    curl iputils-ping dnsutils git

# eBPF / BCC tooling (required for the Telemetry Agent)
sudo apt install -y bpfcc-tools python3-bpfcc linux-headers-$(uname -r)
```

> **Note:** `bpfcc-tools` and `python3-bpfcc` are installed via `apt`, **not** `pip`. The `requirements.txt` for the telemetry agent lists `bcc` as a reminder only; the apt packages take precedence.

---

### 5.2 Docker Desktop (Windows)

1. Download and install **Docker Desktop** from [https://www.docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop).
2. In Docker Desktop → **Settings → General**, enable **"Use the WSL 2 based engine"**.
3. Under **Settings → Resources → WSL Integration**, toggle on your Ubuntu distro.
4. Restart Docker Desktop and confirm it is running (system tray icon).

Verify from WSL2:
```bash
docker --version
docker compose version
```

---

### 5.3 Python Virtual Environments

Create an isolated virtual environment for each Python service to avoid package conflicts.

#### Telemetry Agent
```bash
cd acds/telemetry

python3 -m venv .venv
source .venv/bin/activate

# bcc is provided by the system apt package, not pip
pip install confluent-kafka>=2.3.0 jsonschema>=4.0.0

deactivate
cd ../..
```

> **Important:** The `bcc` Python bindings come from the system package `python3-bpfcc`. You must either activate the venv with `--system-site-packages` or simply run `agent.py` with the system Python3 (outside a venv), since system site-packages include BCC:

```bash
# Easiest approach — use system Python3 for the agent:
pip3 install --user confluent-kafka jsonschema
```

#### DPI Service
```bash
cd dpi_service

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
deactivate
cd ..
```

#### Correlation Service
```bash
cd acds/correlation_service

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
deactivate
cd ../..
```

#### Backend API
```bash
cd acds/ui/backend

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
deactivate
cd ../../..
```

---

### 5.4 Node.js & Frontend Dependencies

#### Install Node.js (via nvm — recommended)
```bash
# Install nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc

# Install Node.js LTS
nvm install --lts
nvm use --lts
node --version   # should show v18.x or higher
```

#### Install Frontend Node Modules
```bash
cd acds/ui/frontend
npm install
cd ../../..
```

---

## 6. One-Time Configuration

No manual path editing is needed. **`open_terminals.sh` automatically detects the project root** relative to its own location, so it works wherever the repo is cloned.

### sudo Password (prompted at runtime)

When you run `open_terminals.sh`, it will securely **prompt you for your WSL2 sudo password** before launching:

```
[ACDS] Enter your WSL sudo password:
```

This password is used only to start `agent.py` and `dpi_main.py`, which need root access for eBPF kernel probes and raw packet capture. It is **never stored in any file**.

### Optional: NOPASSWD for Python (skip the prompt)

If you want the script to launch without any password prompt, add a sudoers rule:

```bash
sudo visudo
```

Add at the bottom (replace `yourusername`):
```
yourusername ALL=(ALL) NOPASSWD: /usr/bin/python3
```

---

## 7. Running the Full Stack

### 7.1 Using `open_terminals.sh` (Recommended)

This script performs the following automatically:

1. **Stops** any existing Kafka/Zookeeper Docker containers
2. **Starts** fresh containers (`docker compose up -d`) and waits 15 seconds for them to become healthy
3. **Opens 6 Windows Terminal tabs**, one for each service:

| Tab | Service | Command |
|-----|---------|---------|
| 🧠 Telemetry Agent | eBPF kernel probe → Kafka | `sudo python3 agent.py` |
| 🌊 DPI Service | Packet capture → Kafka | `sudo python3 dpi_main.py` |
| 🔗 Correlation Service | Kafka correlator → enriched events | `python3 correlation_main.py` |
| ⚡ Python API Backend | FastAPI on port 8000 | `uvicorn server:app --host 0.0.0.0 --port 8000` |
| 🌐 React UI Frontend | Vite dev server on port 5173 | `npm run dev -- --host 0.0.0.0 --port 5173` |
| 📨 Kafka Monitor | Console consumer for live messages | `kafka-console-consumer ...` |
| 🔁 Traffic Generator | Continuous synthetic traffic | `./scripts/generate_traffic.sh` |

**Run from inside WSL2** (from the repo root):

```bash
# Navigate to wherever you cloned the repo
cd /path/to/ACDS

chmod +x scripts/open_terminals.sh scripts/generate_traffic.sh
./scripts/open_terminals.sh
```

---

### 7.2 Manual Step-by-Step

If you prefer to start each component yourself (e.g., on a headless server or without Windows Terminal), follow these steps **in order**, each in a separate terminal.

> All commands below assume you are running from inside the **repo root directory** (the folder you cloned into).

#### Step 1 — Start Kafka Stack (Docker)

```bash
cd acds/telemetry
docker compose down          # stop any old containers
docker compose up -d         # start Zookeeper + Kafka + Kafka-UI
sleep 15                     # wait for Kafka to be ready
docker compose ps            # verify all 3 services are "Up"
cd ../..
```

#### Step 2 — Start the Telemetry Agent

```bash
# Must run as root for eBPF kprobe access
sudo python3 acds/telemetry/agent/agent.py
```

Expected output:
```
[INFO] Starting ACDS Telemetry Agent (Python+BCC)...
[INFO] Compiling eBPF program...
[INFO] Successfully attached kernel kprobes.
[INFO] Agent active and polling perf buffers.
```

#### Step 3 — Start the DPI Service

```bash
# Must run as root for raw packet capture (Scapy)
sudo python3 dpi_service/dpi_main.py
```

Expected output:
```
============================================================
  ACDS DPI SERVICE  —  Layer 5
  Capture: TCP + UDP | Bidirectional flows | Kafka→dpi.features
============================================================
```

#### Step 4 — Start the Correlation Service

```bash
cd acds/correlation_service
python3 correlation_main.py
```

Expected output:
```
=================================================================
  ACDS CORRELATION SERVICE  —  Layer 6
  Consuming: telemetry.raw, dpi.features
  Publishing: enriched.flows
=================================================================
```

#### Step 5 — Start the Backend API

```bash
cd acds/ui/backend
python3 -m uvicorn server:app --host 0.0.0.0 --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

#### Step 6 — Start the React Frontend

```bash
cd acds/ui/frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

Expected output:
```
  VITE v7.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: http://0.0.0.0:5173/
```

---

## 8. Generating Test Traffic

The `generate_traffic.sh` script runs in an infinite loop, generating synthetic network events so the pipeline has data to process even in a quiet environment.

```bash
# From the repo root:
chmod +x scripts/generate_traffic.sh
./scripts/generate_traffic.sh
```

What it generates every ~1 second:

| Type | Tool | Target |
|------|------|--------|
| **TCP/HTTPS** | `curl` | google.com, cloudflare.com |
| **ICMP (ping)** | `ping -c 1` | 8.8.8.8, 1.1.1.1 |
| **DNS** | `nslookup` | example.com, github.com |

A `.` is printed to the console every iteration to confirm it is running. Press **Ctrl+C** to stop.

> This script is automatically launched in the **🔁 Traffic Generator** tab when using `open_terminals.sh`.

---

## 9. Accessing the UI & Services

Once all services are running, open these URLs in your **Windows browser**:

| Service | URL | Description |
|---------|-----|-------------|
| **React Dashboard** | http://localhost:5173 | Main UI — live telemetry, DPI flows, threat scores |
| **FastAPI Docs** | http://localhost:8000/docs | Swagger UI for the REST API |
| **API Status** | http://localhost:8000/api/status | Kafka connection health |
| **Live Events** | http://localhost:8000/api/events | Last 100 raw telemetry events |
| **Threats** | http://localhost:8000/api/threats | Enriched + risk-scored flow events |
| **Kafka UI** | http://localhost:8080 | Browse Kafka topics and messages |

### WebSocket Endpoints

| WebSocket | Description |
|-----------|-------------|
| `ws://localhost:8000/ws/telemetry` | Real-time `telemetry.raw` stream |
| `ws://localhost:8000/ws/threats` | Real-time `enriched.flows` stream |

---

## 10. Stopping the Stack

### Stop All Services

Press **Ctrl+C** in each terminal tab to stop its service, then:

```bash
# From the repo root, stop and remove Kafka containers:
cd acds/telemetry
docker compose down
```

### Stop Docker Completely (Optional)

Right-click the Docker Desktop icon in the Windows system tray → **Quit Docker Desktop**.

---

## 11. Troubleshooting

### eBPF / BCC Errors

| Error | Solution |
|-------|----------|
| `FATAL: bcc module not found` | Run `sudo apt install bpfcc-tools python3-bpfcc` |
| `Failed to attach kprobes` | Ensure you are running `agent.py` with `sudo` |
| `Cannot find eBPF C program` | Verify `acds/telemetry/ebpf/telemetry.c` exists |
| BPF compile errors | Ensure kernel headers are installed: `sudo apt install linux-headers-$(uname -r)` |
| `clock_gettime` error | Kernel < 5.8; upgrade WSL2 kernel via Windows Update |

### Kafka / Docker Errors

| Error | Solution |
|-------|----------|
| `docker compose` not found | Update Docker Desktop; use `docker compose` (no hyphen) |
| Kafka not ready | Increase `sleep` from 15 to 30 seconds in `open_terminals.sh` |
| Port 9092 already in use | Kill the old container: `docker compose down` then `up -d` |
| `< 3 services running` warning | Restart Docker Desktop and retry |

### Kafka Consumer Errors (Python services)

| Error | Solution |
|-------|----------|
| `NoBrokersAvailable` | Kafka is not yet ready; wait 15–30 s after `docker compose up` |
| `KAFKA_BOOTSTRAP_SERVERS` ignored | Services default to `localhost:9092`; ensure Kafka is on that port |

### DPI Service

| Error | Solution |
|-------|----------|
| `Permission denied` on Scapy | Run `dpi_main.py` with `sudo` |
| No packets captured | Verify network interface is active; Scapy sniffs the default interface |

### Frontend

| Error | Solution |
|-------|----------|
| `npm install` fails | Ensure Node.js ≥ 18; run `nvm use --lts` |
| Blank dashboard | Check that the Backend API on port 8000 is running |
| WebSocket disconnecting | Confirm CORS middleware is configured (it allows `*` by default) |

### `open_terminals.sh` Issues

| Error | Solution |
|-------|----------|
| `wt.exe` not found | Install Windows Terminal from the Microsoft Store |
| `ERROR: Cannot find telemetry dir` | Ensure you run the script from inside WSL2, not from PowerShell/CMD |
| Tabs open but services crash immediately | Check individual service logs for Python import errors |

---

## Python Dependency Summary

| Service | Key Packages |
|---------|-------------|
| **Telemetry Agent** | `bcc` (apt), `confluent-kafka≥2.3.0`, `jsonschema≥4.0.0` |
| **DPI Service** | `scapy≥2.5.0`, `numpy≥1.24.0`, `confluent-kafka≥2.3.0` |
| **Correlation Service** | `aiokafka≥0.8.1` |
| **Backend API** | `fastapi≥0.103.1`, `uvicorn[standard]≥0.23.2`, `aiokafka≥0.8.1`, `websockets≥11.0.3`, `pydantic≥2.3.0`, `python-multipart≥0.0.6` |

## Frontend Dependency Summary

| Package | Version | Purpose |
|---------|---------|---------|
| `react` + `react-dom` | ^19.2.0 | UI framework |
| `react-router-dom` | ^7.13.1 | Client-side routing |
| `recharts` | ^3.7.0 | Charts and graphs |
| `lucide-react` | ^0.576.0 | Icon library |
| `date-fns` | ^4.1.0 | Date formatting |
| `react-window` | ^1.8.10 | Virtualised lists |
| `vite` | ^7.3.1 | Dev server & bundler |
| `tailwindcss` | ^4.2.1 | CSS utility framework |
