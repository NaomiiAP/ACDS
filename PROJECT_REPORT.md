# Autonomous Cyber Defense System (ACDS)

## Mini Project Report

---

## 1. Introduction

### 1.1 Problem Statement

Modern enterprise networks generate massive volumes of telemetry data across kernel syscalls, network packets, and application logs. Traditional security tools like signature-based IDS/IPS fail to detect zero-day attacks, encrypted command-and-control (C2) channels, and lateral movement within containerized environments. Security analysts are overwhelmed by alert fatigue, with false positive rates exceeding 90% in many SOC deployments.

### 1.2 Proposed Solution

ACDS is a **real-time, autonomous cyber defense platform** that combines:

- **Kernel-level telemetry** via eBPF probes for syscall-level visibility
- **Deep Packet Inspection** on encrypted traffic without decryption
- **Hybrid ML detection** using a 4-model ensemble (supervised + unsupervised)
- **LLM-based triage** for human-readable threat explanations
- **Graph-based attack tracking** with risk propagation in Neo4j
- **Real-time React dashboard** with live WebSocket streaming

### 1.3 Key Innovation

ACDS operates as a **7-layer autonomous defense pipeline** where each layer enriches the data from the previous one, culminating in a fully attributed, ML-scored, LLM-explained alert with attack graph context -- all in under 5 seconds from kernel event to dashboard.

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
+------------------+     +------------------+     +---------------------+
|  eBPF Telemetry  |---->|                  |---->|   ML Detection      |
|  Agent (Kernel)  |     |                  |     |   (4-Model Ensemble)|
+------------------+     |    Correlation   |     +----------+----------+
                         |    Service       |                |
+------------------+     |  (Flow Enrichment|     +----------v----------+
|  DPI Service     |---->|   & Risk Scoring)|     |   LLM Triage        |
|  (Packet Capture)|     |                  |     |   (Ollama/Llama3.2) |
+------------------+     +--------+---------+     +----------+----------+
                                  |                          |
                         +--------v---------+     +----------v----------+
                         |  Backend API     |     |   Attack Graph      |
                         |  (FastAPI + WS)  |     |   (Neo4j + Risk     |
                         +--------+---------+     |    Propagation)     |
                                  |               +---------------------+
                         +--------v---------+
                         |  React Dashboard |
                         |  (Real-time UI)  |
                         +------------------+
```

### 2.2 Data Flow Pipeline

```
Kernel Syscalls ──> telemetry.raw ──┐
                                    ├──> Correlation ──> enriched.flows ──> ML Detection ──> ml.alerts ──> LLM Triage ──> triage.results
Network Packets ──> dpi.features ──┘                                                            |                              |
                                                                                                └──────> Attack Graph <────────┘
                                                                                                              |
                                                                                          Backend API <───────┘
                                                                                              |
                                                                                        React Dashboard
```

### 2.3 Kafka Topic Flow

| Topic | Producer | Consumer(s) |
|-------|----------|-------------|
| `telemetry.raw` | Telemetry Agent | Correlation Service, Backend API |
| `dpi.features` | DPI Service | Correlation Service |
| `enriched.flows` | Correlation Service | ML Detection, Backend API |
| `ml.alerts` | ML Detection | LLM Triage, Graph Service, Backend API |
| `triage.results` | LLM Triage | Graph Service, Backend API |

---

## 3. Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Kernel Probes | eBPF/BCC | Syscall interception (connect, execve) |
| Packet Capture | Scapy | Raw packet capture and feature extraction |
| Message Bus | Apache Kafka | Async event streaming between services |
| ML Framework | XGBoost, scikit-learn, PyTorch | Model training and inference |
| ML Inference | ONNX Runtime | Production-optimized model serving |
| LLM Engine | Ollama + Llama 3.2 | Local, privacy-preserving alert triage |
| Graph Database | Neo4j 5 | Attack graph storage and traversal |
| Backend API | FastAPI + WebSocket | REST API and real-time streaming |
| Frontend | React 19 + Vite + TailwindCSS | Real-time security dashboard |
| Containers | Docker Compose | Infrastructure orchestration |
| Platform | WSL2 (Ubuntu 22.04) on Windows | Development and deployment |

---

## 4. Module Descriptions

### 4.1 Telemetry Agent (Layer 4 - Kernel)

**Purpose:** Capture every network connection and process execution at the kernel level using eBPF kprobes.

**How It Works:**
1. Compiles and loads an eBPF C program into the Linux kernel
2. Attaches kprobes to `tcp_connect`, `inet_csk_accept`, and `sys_execve` syscalls
3. For each intercepted event, extracts: PID, process name, source/destination IP:port, protocol, container ID
4. Publishes structured JSON events to the `telemetry.raw` Kafka topic

**Key Technical Details:**
- Uses BCC (BPF Compiler Collection) Python bindings
- Perf buffer for kernel-to-userspace communication
- Container ID resolution via `/proc/<pid>/cgroup`
- Sub-millisecond overhead per syscall

**Output Schema:**
```json
{
  "timestamp": 1690000000,
  "pid": 1234,
  "process_name": "nginx",
  "syscall": "connect",
  "protocol": "TCP",
  "src_ip": "10.0.0.5",
  "dst_ip": "8.8.8.8",
  "dst_port": 443,
  "container_id": "abcd1234",
  "host_id": "host-01"
}
```

### 4.2 DPI Service (Layer 5 - Network)

**Purpose:** Capture network packets and extract statistical features from traffic flows -- including encrypted traffic -- without decryption.

**How It Works:**
1. Captures raw packets using Scapy on the default network interface
2. Groups packets into bidirectional flows (keyed by src/dst IP:port pairs)
3. For each flow, computes statistical features:
   - **Shannon entropy** of payload bytes (detects encrypted/obfuscated traffic)
   - **Average packet size** and byte distribution
   - **Burst rate** (packet frequency spikes)
   - **Inter-arrival time** (timing analysis for C2 detection)
   - **JA3/JA3S fingerprints** (TLS client/server fingerprinting)
4. Publishes features to `dpi.features` Kafka topic on flow completion or timeout

**Key Technical Details:**
- Flow timeout: 30 seconds idle
- Flow buffer limit: 20 packets per flow
- JA3 fingerprinting for TLS version/cipher identification
- No payload decryption required -- features are purely statistical

### 4.3 Correlation Service (Layer 6 - Attribution)

**Purpose:** Correlate kernel-level process identity with network-level traffic features to produce fully attributed, risk-scored flow events.

**How It Works:**
1. Consumes `telemetry.raw` events and maintains an Active Connection Registry (in-memory, TTL-based)
2. Consumes `dpi.features` events and correlates them with process metadata from the registry
3. Computes an initial risk score based on:
   - Destination port reputation
   - Entropy thresholds (high entropy = possible encryption/exfiltration)
   - Connection frequency anomalies
   - Known-bad IP matching
4. Publishes enriched events to `enriched.flows` with full process + network attribution

**Key Innovation:** Links "which process" (from eBPF) with "what network behavior" (from DPI) to produce attributed flows that ML can act on.

### 4.4 ML Detection Service (Layer 7 - Intelligence)

**Purpose:** Score every enriched flow using a 4-model hybrid ML ensemble and produce alerts for high-scoring threats.

#### 4.4.1 Feature Pipeline

The ML service maintains **sliding time windows** (10s, 30s, 60s) per source IP to compute aggregate behavioral features. The unified 14-element feature vector:

| # | Feature | Detection Target |
|---|---------|-----------------|
| 1 | connection_frequency | DDoS, scanning |
| 2 | avg_packet_size | Data exfiltration |
| 3 | entropy | Encryption, obfuscation |
| 4 | burst_rate | Flooding attacks |
| 5 | inter_arrival_time | C2 beaconing |
| 6 | tls_fingerprint_encoded | Malware TLS fingerprints |
| 7 | window_10s_count | Short-burst attacks |
| 8 | window_30s_count | Medium-term patterns |
| 9 | window_60s_count | Sustained attacks |
| 10 | window_avg_entropy | Persistent encryption |
| 11 | window_max_burst | Peak burst detection |
| 12 | window_unique_dst_ports | Port scanning |
| 13 | process_connection_count | Lateral movement |
| 14 | container_unique_dst_ips | Container breakout scanning |

#### 4.4.2 Model Architecture

**Supervised Models (trained on labeled attack datasets):**

| Model | Algorithm | Weight | Training Data |
|-------|-----------|--------|--------------|
| XGBoost | Gradient Boosted Trees (300 estimators, depth 8) | 0.35 | CICIDS2017 + UNSW-NB15 |
| RandomForest | Random Forest (200 estimators, depth 12) | 0.25 | CICIDS2017 + UNSW-NB15 |

**Unsupervised Models (anomaly detection):**

| Model | Algorithm | Weight | Training Strategy |
|-------|-----------|--------|-------------------|
| Autoencoder | Neural Network (14-8-4-8-14) | 0.25 | Benign traffic only; anomaly = high reconstruction error |
| IsolationForest | Tree-based isolation (200 estimators) | 0.15 | Full dataset; contamination = 5% |

**Ensemble Formula:**
```
ensemble_score = (xgb * 0.35 + rf * 0.25 + ae * 0.25 + if * 0.15)
```

#### 4.4.3 Training Results

Trained on 5.6M samples (2.8M CICIDS2017 + 2.8M UNSW-NB15), balanced to 9.8M with SMOTE:

| Model | F1 Score | Precision | Recall | Accuracy |
|-------|----------|-----------|--------|----------|
| **XGBoost** | 0.9956 | 0.9931 | 0.9980 | 0.9956 |
| **RandomForest** | 0.9924 | 0.9861 | 0.9988 | 0.9924 |

5-fold stratified cross-validation with standard deviation < 0.0002 across all folds.

#### 4.4.4 Dynamic Threshold Management

- Maintains a rolling window of the last 10,000 ensemble scores
- Target false positive budget: 1%
- Threshold updates every 60 seconds based on score distribution
- Risk levels: critical (>= 0.85), high (>= 0.70), medium (>= 0.50), low (< 0.50)

#### 4.4.5 ONNX Deployment

All 4 models are exported to ONNX format for production inference:
- XGBoost: `xgboost.onnx` (2.1 MB)
- RandomForest: `random_forest.onnx` (11.9 MB)
- Autoencoder: `autoencoder.onnx` (2.6 KB)
- IsolationForest: `isolation_forest.onnx` (1.2 MB)

ONNX Runtime provides cross-platform, hardware-accelerated inference with CUDA GPU support.

### 4.5 LLM Triage Service (Layer 8 - Reasoning)

**Purpose:** Provide human-readable explanations for ML-flagged alerts using a local LLM, mapping to MITRE ATT&CK stages.

**How It Works:**
1. Consumes `ml.alerts` from Kafka (filters: ensemble_score >= 0.5)
2. Builds a structured prompt containing:
   - Alert metadata (IPs, ports, process, container)
   - ML scores (ensemble, supervised, unsupervised)
   - Feature values (entropy, burst rate, timing)
   - Risk reasons from ML service
3. Sends prompt to Ollama (local Llama 3.2, 3B parameters)
4. Parses LLM response into structured fields
5. Publishes to `triage.results` Kafka topic

**LLM Output Structure:**
```
EXPLANATION: <1-3 sentence analysis>
ATTACK_STAGE: <MITRE ATT&CK stage>
CONFIDENCE: <low|medium|high>
SEVERITY: <informational|low|medium|high|critical>
MITIGATION: <bullet-pointed remediation steps>
```

**Key Design Decisions:**
- **Local LLM (Ollama)**: No data leaves the network -- privacy-preserving
- **Structured prompts**: Constrained output format for reliable parsing
- **Threshold filter**: Only triages high-confidence alerts to manage LLM throughput

### 4.6 Attack Graph Service (Layer 9 - Context)

**Purpose:** Build and maintain a live attack graph in Neo4j showing threat progression, with automated risk propagation and attack path ranking.

**Graph Model:**

| Node Type | Properties | Example |
|-----------|-----------|---------|
| Host | ip, hostname, risk_score | `(:Host {ip: "10.0.0.5"})` |
| Container | container_id, risk_score | `(:Container {id: "abc123"})` |
| Process | name, pid, risk_score | `(:Process {name: "nginx"})` |
| IP | address, risk_score | `(:IP {address: "8.8.8.8"})` |

| Edge Type | Meaning |
|-----------|---------|
| CONNECTED_TO | Normal network connection |
| SUSPICIOUS_CONNECTION | ML-flagged connection |
| HOSTS | Host runs container |
| RUNS | Container runs process |

**Risk Propagation Algorithm:**
```
For each node N with neighbors {N1, N2, ...}:
  N.risk = max(N.direct_risk, max(Ni.risk * exp(-0.001 * age_seconds)))
```
- Runs every 30 seconds
- 1-hop + 2-hop propagation
- Time decay prevents stale risks from persisting

**Attack Path Ranking:**
- Finds top-K most dangerous paths through the graph
- Uses shortest path with implicit cost = 1 / risk_score
- Returns full path (nodes + edges) with aggregate risk

### 4.7 Backend API

**Purpose:** Bridge all Kafka streams to the React frontend via REST endpoints and WebSockets.

**Architecture:**
- 4 async Kafka consumers running concurrently
- In-memory circular buffers (10K telemetry, 2K threats, 2K ML alerts, 1K triage)
- WebSocket broadcasting to connected clients
- REST endpoints for historical data queries

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Service health and event counts |
| `/api/events` | GET | Recent telemetry events |
| `/api/stats` | GET | Per-window statistics |
| `/api/threats` | GET | Enriched flows with risk scores |
| `/api/threats/stats` | GET | Threat summary counts |
| `/api/ml/alerts` | GET | ML detection alerts |
| `/api/ml/stats` | GET | ML alert statistics |
| `/api/triage` | GET | LLM triage results |
| `/ws/telemetry` | WS | Real-time telemetry stream |
| `/ws/threats` | WS | Real-time threat stream |
| `/ws/ml-alerts` | WS | Real-time ML alert stream |
| `/ws/triage` | WS | Real-time triage stream |

### 4.8 React Frontend

**Purpose:** Real-time security dashboard with live data visualization.

**Pages:**

1. **Overview Dashboard**: Summary statistics, event rates, protocol breakdown, active hosts/containers
2. **Live Stream**: Real-time telemetry event table with process, IP, and port details
3. **Threats**: Enriched flow visualization with risk scores and filtering
4. **ML Detection**: ML alert browser showing ensemble scores, risk levels, predicted labels, and expandable LLM triage analysis
5. **Attack Graph**: Interactive force-directed graph visualization of Neo4j attack paths
6. **Settings**: UI configuration and preferences

**Tech Stack:** React 19, Vite 7, TailwindCSS 4, Recharts, Lucide icons

---

## 5. Datasets

### 5.1 CICIDS2017

- **Source:** Canadian Institute for Cybersecurity
- **Size:** 2,830,743 samples across 8 CSV files (organized by day of the week)
- **Attack Types:** DDoS, PortScan, Brute Force (FTP/SSH), Botnet, Infiltration, Web Attacks, DoS variants, Heartbleed
- **Features Used:** Total Fwd Packets, Average Packet Size, Fwd IAT Min, Flow IAT Mean, Destination Port, Fwd Header Length, Source IP

### 5.2 UNSW-NB15

- **Source:** University of New South Wales
- **Size:** 2,797,716 samples across 6 CSV files
- **Attack Types:** Fuzzers, Analysis, Backdoors, DoS, Exploits, Generic, Reconnaissance, Shellcode, Worms
- **Features Used:** spkts, smean, sinpkt, dintpkt, dsport, ct_dst_sport_ltm, ct_dst_ltm

### 5.3 Feature Engineering

Both datasets are mapped to a **unified 14-feature vector** through:
- Direct column mapping (e.g., packet sizes, port numbers)
- Synthesized features (e.g., window counts from cumulative source IP grouping)
- Hash encoding (e.g., TLS port fingerprinting via MD5 hash normalized to [0,1])
- SMOTE oversampling for class balancing (12.79% attack ratio balanced to 50%)

---

## 6. Results and Evaluation

### 6.1 Supervised Model Performance (5-Fold Cross-Validation)

| Metric | XGBoost | RandomForest |
|--------|---------|-------------|
| F1 Score | 0.9956 +/- 0.0001 | 0.9924 +/- 0.0002 |
| Precision | 0.9931 | 0.9861 |
| Recall | 0.9980 | 0.9988 |
| Accuracy | 0.9956 | 0.9924 |

### 6.2 Classification Report (Last Fold)

**XGBoost:**
```
              precision    recall  f1-score   support
      Benign       1.00      0.99      1.00    981664
      Attack       0.99      1.00      1.00    981664
    accuracy                           1.00   1963328
```

**RandomForest:**
```
              precision    recall  f1-score   support
      Benign       1.00      0.99      0.99    981664
      Attack       0.99      1.00      0.99    981664
    accuracy                           0.99   1963328
```

### 6.3 Unsupervised Models

| Model | Role | Key Metric |
|-------|------|-----------|
| Autoencoder | Anomaly detection on benign-only training | Reconstruction threshold: 0.52 |
| IsolationForest | Density-based anomaly detection | Contamination: 5%, Precision on anomalies: 36.4% |

The unsupervised models serve as **complementary signals** to the supervised classifiers, catching novel attack patterns not seen in training data.

### 6.4 System Performance

| Metric | Target | Status |
|--------|--------|--------|
| End-to-end latency | < 5 seconds | Achieved |
| Kernel probe overhead | < 1ms/syscall | Achieved |
| ML inference (ONNX) | < 10ms/sample | Achieved |
| Dashboard update rate | Real-time (WebSocket) | Achieved |

---

## 7. Port Reference

| Service | Port | Protocol |
|---------|------|----------|
| Zookeeper | 2181 | TCP |
| Kafka | 9092 | TCP |
| Kafka UI | 8085 | HTTP |
| Neo4j Browser | 7474 | HTTP |
| Neo4j Bolt | 7687 | TCP |
| Ollama LLM | 11434 | HTTP |
| Backend API | 8000 | HTTP/WS |
| Graph API | 8100 | HTTP |
| Frontend | 5173 | HTTP |

---

## 8. Future Scope

1. **Kubernetes Deployment**: DaemonSets for telemetry, HPA for ML workers
2. **MITRE ATT&CK Integration**: Full technique mapping and kill chain visualization
3. **Automated Response**: Policy-based containment (isolate container, block IP)
4. **Multi-host Federation**: Distributed telemetry collection across cluster
5. **Model Retraining Pipeline**: Continuous learning from analyst feedback
6. **SIEM Integration**: Syslog/CEF export for enterprise tool interoperability

---

## 9. Conclusion

ACDS demonstrates a complete, end-to-end autonomous cyber defense pipeline that combines kernel-level observability, encrypted traffic analysis, hybrid ML detection, LLM-powered reasoning, and graph-based attack tracking into a unified platform. The system achieves 99.5%+ F1 scores on standard security benchmarks while providing real-time, human-readable threat intelligence through a modern React dashboard.

The modular, Kafka-based architecture ensures each layer can be independently scaled, updated, or replaced, making it suitable for both development environments and production deployments.

---

## 10. References

1. Sharafaldin, I., Lashkari, A.H., Ghorbani, A.A. (2018). "Toward Generating a New Intrusion Detection Dataset and Intrusion Traffic Characterization." ICISSP 2018.
2. Moustafa, N., Slay, J. (2015). "UNSW-NB15: A Comprehensive Data Set for Network Intrusion Detection Systems." MilCIS 2015.
3. Chen, T., Guestrin, C. (2016). "XGBoost: A Scalable Tree Boosting System." KDD 2016.
4. Liu, F.T., Ting, K.M., Zhou, Z.H. (2008). "Isolation Forest." ICDM 2008.
5. Greenberg, A. (2019). "eBPF-based Observability for Modern Infrastructure." Linux Foundation.
6. MITRE ATT&CK Framework. https://attack.mitre.org/
