# Autonomous Cyber Defense System (ACDS) — Full Implementation Specification

## 1. Executive Summary
ACDS is a Kubernetes-deployable, microservice-based autonomous SOC that ingests kernel-level telemetry (via eBPF), enriches traffic via lightweight DPI, detects known and unknown attacks using a hybrid ML pipeline, uses a local LLM to triage and explain alerts, continuously updates an attacker attack-graph (Neo4j), and executes policy-driven automated responses (container isolation, IP blocking, rate limits) with human-in-the-loop overrides and a feedback retraining loop.

## 2. System Goals & Non-Functional Requirements

### Functional Goals
*   **Real-time telemetry capture**: Kernel + network level.
*   **DPI**: Extract behavior-rich features (including encrypted flows).
*   **Hybrid detection**: Supervised + unsupervised with ensemble scoring.
*   **LLM-based triage**: Human-readable summaries & mitigation suggestions.
*   **Real-time dynamic attack graph**: GNN-inspired scoring.
*   **Policy-driven self-healing**: Automated actions with human override.
*   **Retraining pipeline**: Feedback loop for model improvement.

### Non-Functional
*   **Latency**: End-to-end detection & triage pipeline < 5s (target).
*   **Throughput**: Scale horizontally via Kafka + Kubernetes.
*   **Resilience**: Service restarts, HPA for ML & DPI workers.
*   **Privacy**: No payload decryption; local/offline LLM runtime only.
*   **Security**: TLS, Kubernetes RBAC, secrets for model keys, audit logs.
*   **Observability**: Prometheus + Grafana metrics, central logs.

## 3. Team Responsibilities
*   **Pranav M.K.** — Telemetry Collection: eBPF probes, kernel hooks, topic schema, serialization into message bus.
*   **Prapti** — DPI & Feature Extraction: packet parsing, JA3/JA3S, entropy, byte distributions, building feature vectors.
*   **Naomi & Pranav S.** — Steps 3–7: ML detection, triage (LLM), attack graph (Neo4j), self-healing, logging, retraining.

## 4. High-Level Architecture & Components

### Services (Microservices) and Data Flows
1.  **Telemetry Collector (eBPF)**: Runs on each host/node, collects flow metadata + process/container mapping + syscall traces. Publishes to Kafka topic `telemetry.raw`.
2.  **Message Bus**: Apache Kafka (or Redis Streams). Topics: `telemetry.raw`, `dpi.features`, `ml.alerts`, `triage.requests`, `policy.actions`.
3.  **DPI & Feature Extraction Service**: Consumes `telemetry.raw`, performs DPI & behavioral extraction. Outputs to `dpi.features`.
4.  **Detection Service (ML)**: Consumes `dpi.features`. Uses Supervised (XGBoost/RF) and Unsupervised (Autoencoder) models. Outputs `ml.alerts`.
5.  **LLM Triage Service**: Local LLM behind an API. Generates human-readable reports and suggestions. Writes to `triage.results`.
6.  **Attack Graph Service (Neo4j)**: Receives `triage.results` and `ml.alerts`. Updates nodes (hosts, containers, etc.) and edges. Computes progression metrics.
7.  **Policy Engine (OPA / YAML)**: Evaluates safe actions based on alerts and scores. Emits `policy.actions`.
8.  **Enforcer / Remediation Service**: Implements actions (iptables, eBPF maps, K8s network policies).
9.  **Logging, Metrics & Retraining**: FluentBit -> ELK/Loki; Prometheus metrics; Retraining pipeline.
10. **Admin & UI**: React dashboard for monitoring and policy management.

## 5. Data Contracts & Message Schemas

### `telemetry.raw` (from eBPF)
```json
{
  "timestamp": 1690000000,
  "host_id": "node-01",
  "proc_id": 1234,
  "proc_name": "nginx",
  "container_id": "abcd1234",
  "src_ip": "10.0.0.5",
  "src_port": 52341,
  "dst_ip": "8.8.8.8",
  "dst_port": 443,
  "protocol": "TCP",
  "bytes_sent": 200,
  "bytes_recv": 1024,
  "syscall_event": "connect",
  "kmeta": {...}
}
```

### `dpi.features`
```json
{
  "flow_id": "...",
  "ja3": "...",
  "ja3s": "...",
  "entropy": 4.2,
  "byte_distribution": [0.1, 0.05, ...],
  "avg_pkt_size": 512,
  "burstiness": 0.8,
  "tls_version": "1.3",
  "time_window": 10,
  "host_context": {"proc_name":"...","container":"..."}
}
```

### `ml.alert`
```json
{
 "alert_id":"a123",
 "flow_id":"...",
 "supervised_score":0.86,
 "unsupervised_score":0.72,
 "ensemble_score":0.82,
 "features":["..."],
 "timestamp": "...",
 "recommended_action": "isolate_container"
}
```

### `policy.action`
```json
{
 "action_id":"p123",
 "alert_id":"a123",
 "action":"isolate_container",
 "target":"container_id",
 "status":"pending/approved/executed",
 "requested_by":"policy_engine",
 "human_override_required": true
}
```

## 6. Telemetry Collection (Pranav's Scope)

### Design Goals
*   High fidelity, low overhead, trustworthy process association.

### Components
*   **eBPF programs (C)**: Managed via libbpf-bpftrace or BCC.
*   **Userspace agent (Python/Go)**: Load programs, read perf buffers, augment with metadata.

### What to Capture
*   Flow metadata (IPs, ports, protocols).
*   TLS handshake metadata (JA3/JA3S).
*   Timing characteristics (inter-packet time, burst metrics).
*   Process-context mapping (PID -> Container ID/Image).
*   Lateral movement syscalls (connect, execve, open).

### Implementation Notes
*   **Kernel**: Linux 5.x+ (libbpf).
*   **Tools**: bpftool, bcc, libbpf, clang.
*   **Reliability**: Sequence numbers, local buffering, backpressure handling.

## 7. DPI & Feature Extraction (Prapti's Scope)

### Design Goals
*   Extract ML features from encrypted traffic without decryption.

### Feature Categories
*   **Protocol & Header**: Flags, port types, packet sizes.
*   **TLS Fingerprints**: JA3/JA3S, cipher suite, version.
*   **Statistical**: Entropy, byte distribution, average packet size.
*   **Temporal**: Inter-packet timings, burstiness, duration.
*   **Contextual**: Process name, container image, user.

### Implementation
*   Scapy or Python socket/tshark integrations.
*   Compute Shannon entropy and byte histograms.
*   Normalize vectors and handle categorical data.

## 8. Machine Learning Detection (Naomi & Pranav S)

### Models
*   **Supervised**: XGBoost/RandomForest on CICIDS2017/UNSW-NB15.
*   **Unsupervised**: Autoencoder/IsolationForest for anomaly detection.
*   **Ensemble**: Weighted combination/stacking of model outputs.

### Engineering & Training
*   Time windows (10s, 30s, 1min) for aggregation.
*   Process/container aggregations for lateral movement.
*   Cross-validation and class balancing (SMOTE).

### Operationalization
*   API: FastAPI + ONNX/PyTorch.
*   Model Versioning: Registry for binaries and metadata.
*   Dynamic Thresholds: Based on false positive budget.

## 9. LLM Triage (Naomi & Pranav S)

### Purpose
*   Provide readable explanations, attack stage inference, and mitigation steps.

### Design
*   **Local LLM**: Ollama/LM Studio/HF (offline).
*   **Prompts**: Structured templates using ML alerts, flow context, and Neo4j data.
*   **Safety**: Suggestions only; no direct execution by LLM.

## 10. Attack Graph & Graph Scoring (Naomi & Pranav S)

### Graph Model
*   **Nodes**: Host, Container, Process, Account, IP, Service.
*   **Edges**: connected_to, auth_by, spawned, suspicious_connection.
*   **Scoring**: Time-decayed risk propagation and path ranking (Neo4j GDS).

## 11. Policy Engine & Safe Automation

### Design Principles
*   Least privilege, Human-in-the-loop, Rate limiting.
*   **Format**: YAML-based rules (e.g., `id: block_external_ssh`).

## 12. Enforcer / System Control

### Actions
*   Block IP (iptables/eBPF).
*   Isolate container (K8s NetworkPolicy).
*   Pause/Evict container.
*   Throttle network (tc).

## 13. Logging, Metrics & Observability
*   **Logs**: FluentBit -> ELK/Loki.
*   **Metrics**: Prometheus exporters + Grafana dashboards.
*   **Auditing**: Immutable logs for all remediation actions.

## 14. Deployment & Infra
*   **Kubernetes**: Namespaces (`acds-system`, etc.), DaemonSets (telemetry), Deployments (HPA for ML/DPI).
*   **Storage**: Neo4j PV, S3/Minio for datasets.
*   **Secrets**: K8s secrets for certs and model keys.

## 15. Security & Privacy Considerations
*   Local LLM to prevent telemetry leakage.
*   Encrypted Kafka traffic (SASL/TLS).
*   RBAC for Neo4j and Enforcer.
*   Anonymize PII in logs.

## 16. Testing & Validation Plan
*   **Unit/Integration**: eBPF parsing, Kafka topics, end-to-end pipeline.
*   **Scenarios**: Metasploit/Nmap simulations on CICIDS2017/UNSW-NB15 datasets.
*   **Red-Team**: Controlled exploit chains and canary hosts.
*   **Performance**: Latency benchmarking at 95th percentile.

## 17. CI/CD & Model Ops
*   **CI**: GitHub Actions for builds and image registry.
*   **CD**: ArgoCD/GitOps.
*   **Model Ops**: MLflow tracking and canary rollouts.

## 18. Monitoring & Operational Runbook
*   eBPF reload commands.
*   Kafka/Neo4j/LLM restart procedures.
*   Action approval/rollback in UI.
*   Sentry alerts for high FP rates.

## 19. Deliverables & Folder Layout
```
/acds
  /telemetry       (eBPF probes, userspace agent)
  /dpi             (parser, feature extraction)
  /ml              (models, trainer, server)
  /llm             (prompt templates, api)
  /graph           (neo4j schema, graph api)
  /policy_engine   (policies, engine)
  /enforcer        (k8s, iptables scripts)
  /ui              (react app)
  /deploy          (helm charts, k8s manifests)
  /docs            (architecture, runbook, api_spec)
  Dockerfile
  README.md
```

## 20. Step-by-Step Setup Guide

### Prereqs
*   Linux 5.x+, Docker, Kubernetes (Minikube/Kind), Kafka, Neo4j, Python 3.10+.
*   Tools: `bpftool`, `clang`, `libbpf`, `bcc`.

### Quickstart
1.  **Build eBPF**: `clang -O2 -target bpf -c ebpf/telemetry.c -o telemetry.o`
2.  **Run Agent**: `cd telemetry/agent && python agent.py --kafka brokers:9092`
3.  **Start Infra**: `docker-compose -f infra/docker-compose.dev.yml up -d`
4.  **Start DPI**: `cd dpi && python dpi_service.py`
5.  **Deploy ML/UI**: `kubectl apply -f deploy/ml-deployment.yaml` etc.

## 21. API & Integration Endpoints
*   `POST /score`: Features -> ML Alert.
*   `POST /triage`: Alert + Context -> Triage Result.
*   `POST /policy/evaluate`: Alert + Triage -> Policy Action.
*   `POST /enforce`: Action -> Status.

## 22. Example Flows
*   **Scenario A (Known Exploit)**: SSH anomaly -> ML Score > 0.9 -> LLM Summary -> Analyst Approval -> Container Isolation.
*   **Scenario B (Zero-day)**: Unusual short connections -> High Anomaly Score -> Attack Graph rising risk -> Auto-block IPs + Throttling.

## 23. Metrics to Track (KPIs)
*   TPR/FPR, Precision/Recall.
*   MTTD (Detection), MTTR (Remediation).
*   Analyst interventions per week.
*   Model drift metrics.

## 24. Documentation & Handover
*   `architecture.md`, `api_spec.md`, `deployment_guide.md`, `runbook.md`.

## 25. Next Action Checklist
*   **Pranav (Telemetry)**: eBPF flow prototype, Protobuf schema, Kafka publication.
*   **Prapti (DPI)**: DPI parser, JA3 library, Feature vector normalization.
*   **Naomi & Pranav S (ML/Graph)**: Kafka consumer, XGBoost/Autoencoder base, LLM runtime, Neo4j schema.

## 26. Risks & Mitigations
*   **LLM Hallucination**: Cross-check evidence; policy engine gating.
*   **FP Outages**: Manual approval for high-impact actions; rate limiting.
*   **eBPF Complexity**: Staging tests; kernel pinning; fallbacks.

## 27. Appendix
*   **Load eBPF**: `sudo bpftool prog load telemetry.o /sys/fs/bpf/telemetry type kprobe`
*   **Kafka Produce**: `kafka-console-producer --topic telemetry.raw --broker-list localhost:9092`
*   **Neo4j Create**: `CREATE (h:Host {id:'host-1'})`
