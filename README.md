# ACDS — Adaptive Cyber Defence System

> **Telemetry Layer** — Real-time network and process monitoring using eBPF, Apache Kafka, and a React dashboard.

[![Branch](https://img.shields.io/badge/branch-pranavmk-10b981?style=flat-square)](https://github.com/praptirn/ACDS/tree/pranavmk)
[![Layer](https://img.shields.io/badge/layer-4%20Visualization-14b8a6?style=flat-square)](#architecture)
[![Status](https://img.shields.io/badge/status-active-22c55e?style=flat-square)](#)

---

## Table of Contents

- [What Is ACDS?](#what-is-acds)
- [Architecture](#architecture)
- [Repository Structure](#repository-structure)
- [Components](#components)
  - [Telemetry Agent (eBPF)](#1-telemetry-agent-ebpf)
  - [Kafka Transport](#2-kafka-transport)
  - [API Bridge (FastAPI)](#3-api-bridge-fastapi)
  - [React Dashboard (UI)](#4-react-dashboard-ui)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Quick Start](#quick-start)
- [UI Pages](#ui-pages)
- [API Reference](#api-reference)
- [Event Schema](#event-schema)
- [Traffic Generation](#traffic-generation)
- [Multi-Host Setup](#multi-host-setup)
- [Technology Stack](#technology-stack)

---

## What Is ACDS?

ACDS (**Adaptive Cyber Defence System**) is a distributed network telemetry and monitoring platform. It captures live kernel-level syscall events from any Linux host using **eBPF**, streams them through **Apache Kafka**, and visualizes them in a real-time **React dashboard**.

This branch (`pranavmk`) contains the complete **Layer 4 — Visualization** implementation, including the eBPF telemetry agent, Kafka bridge API, and full React UI.

> **Scope Note:** This layer handles collection, transport, aggregation, and visualization. ML-based threat scoring, DPI, and anomaly classification belong to subsequent layers (DPI Phase).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Linux Host                           │
│                                                             │
│  ┌──────────────┐     ┌──────────────────────────────────┐  │
│  │  eBPF Agent  │────▶│   Kafka Topic: telemetry.raw     │  │
│  │  (BCC/Python)│     │   (Schema v1.0)                  │  │
│  └──────────────┘     └──────────────┬───────────────────┘  │
│                                      │                       │
│                       ┌──────────────▼───────────────────┐  │
│                       │   FastAPI Bridge  :8000           │  │
│                       │   REST + WebSocket                │  │
│                       └──────────────┬───────────────────┘  │
│                                      │                       │
│                       ┌──────────────▼───────────────────┐  │
│                       │   React Dashboard  :5173          │  │
│                       │   Vite + Recharts + Tailwind      │  │
│                       └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

Multiple hosts can publish to the **same Kafka topic** — the dashboard automatically segments telemetry by `host_id` on the Hosts page.

---

## Repository Structure

```
ACDS/
├── acds/
│   ├── telemetry/                  # eBPF Telemetry Agent
│   │   ├── agent/
│   │   │   └── agent.py            # Main eBPF agent (BCC + Kafka producer)
│   │   └── requirements.txt        # Python deps for agent
│   │
│   └── ui/
│       ├── backend/                # FastAPI API Bridge
│       │   ├── server.py           # Main FastAPI app (REST + WebSocket)
│       │   └── requirements.txt    # Python deps for backend
│       │
│       └── frontend/               # React Dashboard
│           ├── src/
│           │   ├── pages/
│           │   │   ├── Dashboard.jsx     # Overview page
│           │   │   ├── LiveStream.jsx    # Real-time event table
│           │   │   ├── Hosts.jsx         # Multi-host management
│           │   │   └── Settings.jsx      # UI settings & diagnostics
│           │   ├── hooks/
│           │   │   └── useTelemetry.js   # WebSocket + stats polling hook
│           │   ├── context/
│           │   │   ├── TelemetryContext.js  # Global event state
│           │   │   └── SettingsContext.js   # Persistent UI settings
│           │   └── App.jsx               # Router + layout
│           └── package.json
│
├── scripts/
│   ├── open_terminals.sh           # Launch full stack in Windows Terminal tabs
│   └── generate_traffic.sh        # Continuous network traffic generator
│
└── README.md
```

---

## Components

### 1. Telemetry Agent (eBPF)

**Location:** `acds/telemetry/agent/agent.py`

Uses **BCC (BPF Compiler Collection)** to attach eBPF probes to the Linux kernel and capture:
- Network connection events (`tcp_connect`, `udp_send`)
- Per-process syscall activity
- Container metadata (via cgroup/namespace inspection)

Each event is serialized as a JSON message and published to Kafka under the `telemetry.raw` topic.

**Event fields captured:**
| Field | Type | Description |
|-------|------|-------------|
| `host_id` | string | Hostname of the capturing machine |
| `pid` | int | Process ID |
| `process_name` | string | Name of the system process |
| `syscall` | string | Kernel syscall intercepted |
| `protocol` | string | `TCP` or `UDP` |
| `src_ip` / `src_port` | string/int | Source address |
| `dst_ip` / `dst_port` | string/int | Destination address |
| `timestamp` | float | Unix timestamp (seconds) |
| `success` | bool | Whether syscall returned success |
| `container_id` | string | Container identifier (empty if bare-metal) |

---

### 2. Kafka Transport

**Topic:** `telemetry.raw`  
**Schema Version:** `v1.0`

Kafka acts as the durable message bus between the eBPF agent and the API bridge. Any number of hosts can publish to the same topic simultaneously.

**Consumer config used by the bridge:**
- `auto_offset_reset = earliest` — ensures historical events are loaded on startup
- `group_id = telemetry-ui-consumer`

---

### 3. API Bridge (FastAPI)

**Location:** `acds/ui/backend/server.py`  
**Port:** `8000`

Consumes the Kafka topic and exposes:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | WebSocket health, Kafka status, total event count |
| `/api/stats` | GET | Rolling statistics (events/sec, TCP/UDP counts, top processes) |
| `/api/events` | GET | Last N raw events (JSON) |
| `/ws/telemetry` | WebSocket | Real-time event stream to the browser |

---

### 4. React Dashboard (UI)

**Location:** `acds/ui/frontend/`  
**Port:** `5173` (Vite dev server)

#### Pages

| Page | Route | Description |
|------|-------|-------------|
| **Overview** | `/` | Event rate chart, protocol donut, stat cards, process bar chart |
| **Live Stream** | `/live` | Virtualized real-time event table with search, filter, export |
| **Hosts** | `/hosts` | Multi-host table with status, click-through host detail view |
| **Settings** | `/settings` | Backend config, connection health, UI behaviour toggles, export |

---

## Getting Started

### Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Linux (WSL2 or native) | Ubuntu 20.04+ | eBPF agent requires kernel ≥ 5.8 |
| Python | 3.8+ | For agent and backend |
| Node.js | 18+ | For the React frontend |
| Apache Kafka | 2.8+ | Must be running on `localhost:9092` |
| BCC (BPF Tools) | Latest | `sudo apt install bpfcc-tools python3-bpfcc` |
| Windows Terminal | Any | For the `open_terminals.sh` launcher (Windows only) |

---

### Quick Start

#### Option 1 — Automated (Windows with WSL)

Open a WSL terminal in the project root and run:

```bash
chmod +x scripts/open_terminals.sh scripts/generate_traffic.sh
./scripts/open_terminals.sh
```

This opens **5 Windows Terminal tabs** automatically:
1. 🧠 **Telemetry Agent** — eBPF kernel probe (`sudo python3 agent.py`)
2. 📨 **Kafka CLI** — live topic consumer for debugging
3. ⚡ **FastAPI Backend** — REST + WebSocket bridge on port `8000`
4. 🌐 **React Frontend** — Vite dev server on port `5173`
5. 🔁 **Traffic Generator** — continuous `curl`/`ping`/`nslookup` loop

Then open **http://localhost:5173** in your browser.

---

#### Option 2 — Manual Step-by-Step

**Step 1 — Start Kafka** (if not already running):
```bash
# Start Zookeeper
bin/zookeeper-server-start.sh config/zookeeper.properties &

# Start Kafka broker
bin/kafka-server-start.sh config/server.properties &
```

**Step 2 — Install agent dependencies:**
```bash
pip3 install -r acds/telemetry/requirements.txt
```

**Step 3 — Start the eBPF Agent** (requires root):
```bash
cd acds/telemetry/agent
sudo python3 agent.py
```

**Step 4 — Install and start the API Bridge:**
```bash
pip3 install -r acds/ui/backend/requirements.txt
cd acds/ui/backend
uvicorn server:app --host 0.0.0.0 --port 8000
```

**Step 5 — Install and start the React frontend:**
```bash
cd acds/ui/frontend
npm install
npm run dev
```

**Step 6 — Generate traffic** (optional, for demo):
```bash
# Open one or more WSL tabs and run:
./scripts/generate_traffic.sh
```

---

## UI Pages

### Overview (Dashboard)
- **Event Flow Rate** — Area chart with selectable time windows: `10s`, `30s`, `1m`, `All`
- **Protocol Distribution** — Live TCP vs UDP donut chart
- **Stat Cards** — Events/sec, Unique Hosts, Active Containers, TCP Connections
- **Active Processes** — Bar chart of top processes by event count
- **Top Processes Table** — Sortable table with activity share percentage bars

### Live Stream
- Virtualized table rendering up to 10,000 events with zero lag
- Search/filter by process name, IP, or host
- Protocol filter (All / TCP / UDP)
- Pause/Resume stream
- Export to CSV
- Click any row to see full event JSON

### Hosts
- Automatic multi-host detection (any machine running the agent appears here)
- Status indicator: 🟢 Active (<5s), 🟡 Idle (<30s), 🔴 Offline (>30s)
- Click any host for the **Host Detail View**:
  - Per-host event rate chart
  - Per-host TCP/UDP split
  - Top destination IPs
  - Top processes
  - Host-filtered live stream (last 50 events)

### Settings
- **Connection Health** — Live WebSocket, Kafka, and Agent heartbeat status
- **Backend Configuration** — Endpoint URLs, Kafka topic, schema version (read-only)
- **UI Behaviour Toggles** (persistent in `localStorage`):
  - Auto-scroll in Live Stream
  - Hide Noisy Processes (init, bash, systemd, sh)
  - Verbose Kernel Timestamps (ISO 8601 format)
- **Demo Mode** toggle
- **Export** — Download last 1,000 / 100 events or stats snapshot as JSON

---

## API Reference

### `GET /api/status`
```json
{
  "kafka_connected": true,
  "total_events": 6872,
  "last_event_ts": 1709500000.0,
  "uptime_seconds": 3620
}
```

### `GET /api/stats?window=10s`
```json
{
  "events_per_sec": 28.4,
  "tcp_count": 110,
  "udp_count": 736,
  "unique_hosts": 1,
  "unique_containers": 1,
  "top_processes": [["curl", 736], ["bash", 226], ["ping", 92]]
}
```

### `GET /api/events?limit=100`
Returns an array of the last N raw event objects.

### `WS /ws/telemetry`
Streams JSON messages in the form:
```json
{ "type": "event", "data": { ...event fields... } }
```

---

## Event Schema

**Schema Version:** `v1.0` — frozen for this sprint.

```json
{
  "host_id": "MK-LAPTOP",
  "pid": 1234,
  "process_name": "curl",
  "syscall": "tcp_connect",
  "protocol": "TCP",
  "src_ip": "192.168.1.10",
  "src_port": 54321,
  "dst_ip": "142.250.180.46",
  "dst_port": 443,
  "timestamp": 1709500000.123,
  "success": true,
  "container_id": "",
  "return_code": 0
}
```

> **Note:** Do not modify this schema without updating the `auto_offset_reset` config and re-validating the API bridge parsing logic.

---

## Traffic Generation

For demos and testing, use the included script:

```bash
./scripts/generate_traffic.sh
```

This loops indefinitely running:
- `curl` requests to popular domains (generates TCP/443 traffic)
- `ping` commands (generates ICMP)
- `nslookup` queries (generates UDP/53 DNS traffic)

Spawn multiple instances simultaneously to increase event rate:
```bash
# In 3 separate WSL tabs:
./scripts/generate_traffic.sh &
./scripts/generate_traffic.sh &
./scripts/generate_traffic.sh
```

---

## Multi-Host Setup

To monitor multiple machines from a single dashboard:

1. Ensure your **Kafka broker is network-accessible** (edit `listeners` in `server.properties`)
2. On each additional host, set the Kafka broker address and run the agent:
   ```bash
   export KAFKA_BOOTSTRAP_SERVERS="<main-machine-ip>:9092"
   sudo python3 acds/telemetry/agent/agent.py
   ```
3. Each host automatically appears as a new row on the **Hosts** page with its own `host_id` (machine hostname)

To simulate a second host on the same machine:
```bash
HOST_ID=SIMULATED-HOST-2 sudo python3 acds/telemetry/agent/agent.py
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Kernel probing | eBPF via BCC (Python) |
| Message transport | Apache Kafka |
| API bridge | FastAPI + Uvicorn + aiokafka |
| Frontend framework | React 18 + Vite |
| Charts | Recharts |
| Styling | Tailwind CSS v4 |
| Virtualized lists | react-window |
| Date formatting | date-fns |
| Icons | lucide-react |

---

## Author

**Pranav M K** — `pranavmkokkada@gmail.com`  
Collaborator on [praptirn/ACDS](https://github.com/praptirn/ACDS)

Branch: [`pranavmk`](https://github.com/praptirn/ACDS/tree/pranavmk)
