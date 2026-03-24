# DPI Service — Deep Packet Inspection Module

> **ACDS Layer 5** — Network flow analysis, feature extraction, and traffic profiling for ML-based threat detection.

---

## Overview

The `dpi_service` is the **Deep Packet Inspection layer** of ACDS. It operates separately from the telemetry layer (eBPF/Kafka) and instead uses **live raw packet capture** via Scapy to reconstruct network flows and extract a rich statistical feature vector from each flow. This feature vector is the intended input to an ML classifier for traffic classification and anomaly detection.

**Current State:** The service is fully implemented at the Flow Manager, Packet Capture, and Feature Extractor layers. The `utils.py` stub and ML classifier integration are placeholders for the next sprint.

---

## Directory Structure

```
dpi_service/
├── dpi_main.py          # Entry point — orchestrates packet → flow → feature pipeline
├── packet_capture.py    # Live packet capture using Scapy (TCP filter, default interface)
├── flow_manager.py      # Groups packets into bidirectional flows with timeout tracking
├── feature_extractor.py # Computes the 6-feature vector from a completed flow
└── utils.py             # Empty stub — reserved for future helpers
```

---

## Data Flow

```
Network Interface (raw TCP packets)
         │
         ▼
 ┌──────────────────┐
 │  packet_capture  │   Scapy sniff() — captures raw TCP packets from default iface
 └────────┬─────────┘
          │ callback: process_packet(packet)
          ▼
 ┌──────────────────┐
 │   flow_manager   │   Groups packets by 5-tuple key (src_ip, dst_ip, sport, dport, proto)
 │                  │   Tracks last-seen timestamp per flow
 └────────┬─────────┘
          │ trigger: when flow has ≥ 20 packets OR times out (10s idle)
          ▼
 ┌──────────────────┐
 │ feature_extractor│   Computes 6-dimensional feature vector from the flow's packets
 └────────┬─────────┘
          │
          ▼
    Feature Vector (dict)  ← [Currently printed to stdout]
          │
          ▼
    [TODO] ML Classifier / Threat Scoring Engine
```

---

## Module Details

### `dpi_main.py` — Orchestrator

The entry point that wires all three components together.

**Key constant:**
```python
FLOW_LIMIT = 20   # Minimum packets before extracting features from an active flow
```

**`process_packet(packet)` function — core logic:**

1. Passes the packet to `flow_manager.add_packet()` to assign it to a flow (5-tuple key)
2. **Trigger 1 — Flow full:** If the flow accumulates ≥ 20 packets, immediately extract features and reset the flow buffer for that key
3. **Trigger 2 — Flow timeout:** On every packet, check for flows idle for >10s. If an expired flow has > 5 packets, extract features before evicting it

This dual-trigger ensures both **high-traffic flows** (trigger every 20 packets) and **low-traffic/short-lived flows** (evicted on timeout) are captured for analysis.

---

### `packet_capture.py` — Raw Packet Capture

Uses **Scapy's `sniff()`** to capture live packets from the network.

```python
sniff(
    prn=callback,   # process_packet is called for every packet
    store=False,    # packets are NOT stored in memory — important for performance
    filter="tcp",   # BPF filter: only capture TCP traffic
    iface=iface     # Scapy's auto-detected default interface
)
```

**Key design decisions:**
- `store=False` — prevents unbounded memory growth at high packet rates
- BPF `"tcp"` filter — restricts to TCP only (UDP/ICMP not currently captured)
- Uses `conf.iface` — picks Scapy's default interface (can be overridden via environment or config)

**Limitation:** Currently only captures TCP. To capture UDP (DNS, QUIC, etc.), the filter should be changed to `"tcp or udp"`.

---

### `flow_manager.py` — Flow State Machine

Maintains two in-memory global data structures:

```python
flows = {}            # Dict[5-tuple → List[packet]]  — packet buffer per flow
flow_last_seen = {}   # Dict[5-tuple → float]         — last packet timestamp per flow
FLOW_TIMEOUT = 10     # seconds of inactivity before a flow is considered expired
```

**Flow Key (5-tuple):**
```python
(src_ip, dst_ip, src_port, dst_port, ip_proto)
# Example: ("192.168.1.5", "142.250.180.46", 54321, 443, 6)
```

**`add_packet(packet)` → key:**
- Extracts 5-tuple from IP layer
- Initializes flow bucket if new
- Appends packet to the bucket
- Updates `flow_last_seen[key]` with current time
- Returns None if packet has no IP layer (skips non-IP traffic)

**`get_expired_flows()` → list of keys:**
- Iterates all tracked flows
- Returns keys where `now - last_seen > 10s`
- Does NOT delete them — deletion is handled by `dpi_main.py` after feature extraction

**Note:** Flows are unidirectional (src→dst only). Bidirectional flow merging (A→B and B→A under the same key) is not yet implemented.

---

### `feature_extractor.py` — Feature Vector Computation

Extracts a **6-dimensional feature vector** from a completed flow's packet list. This is the core of the DPI intelligence and feeds directly into the planned ML classifier.

#### Feature 1 — `connection_frequency`
```python
def connection_frequency(flow):
    return len(flow)
```
Simply the total number of packets in the flow. High values can indicate data exfiltration or scanning.

---

#### Feature 2 — `avg_packet_size`
```python
def average_packet_size(flow):
    sizes = [len(p) for p in flow]
    return sum(sizes) / len(sizes)
```
Mean packet size in bytes. Short packets (< 60 bytes) are typical of SYN scans. Large averages may indicate bulk data transfer.

---

#### Feature 3 — `entropy`
```python
def entropy(flow):
    sizes = [len(p) for p in flow]
    values, counts = np.unique(sizes, return_counts=True)
    probs = counts / counts.sum()
    return -(probs * np.log2(probs)).sum()
```
**Shannon entropy** of the packet size distribution. High entropy means packet sizes are unpredictable/varied — typical of encrypted or tunnelled traffic. Low entropy means all packets are the same size — typical of heartbeat or keep-alive patterns.

---

#### Feature 4 — `burst_rate`
```python
def burst_rate(flow, threshold=0.1):
    times = [p.time for p in flow]
    burst = sum(1 for i in range(len(times)-1) if (times[i+1] - times[i]) < threshold)
    return burst
```
Count of packet pairs where inter-arrival time < 100ms (0.1s). High burst rates indicate rapid-fire transmission — typical of port scanning, DDoS participation, or streaming.

---

#### Feature 5 — `inter_arrival_time`
```python
def inter_arrival_time(flow):
    times = [p.time for p in flow]
    gaps = [times[i+1] - times[i] for i in range(len(times)-1)]
    return sum(gaps) / len(gaps)
```
Mean time (in seconds) between consecutive packets. Low IAT = fast/bursty traffic. High IAT = slow/intermittent — typical of C2 beaconing with long sleep intervals.

---

#### Feature 6 — `tls_fingerprint`
```python
def tls_fingerprint(flow):
    for packet in flow:
        if packet.haslayer("Raw"):
            payload = bytes(packet["Raw"])
            if len(payload) > 5 and payload[0] == 22 and payload[1] == 3:
                version = payload[1:3].hex()
                handshake_type = payload[5]
                return f"TLS_{version}_HS_{handshake_type}"
    return "none"
```
Performs a lightweight **TLS fingerprint** by scanning the raw payload. Checks for the TLS record type byte `0x16` (22 = Handshake) and version bytes `0x03xx`:
- `payload[0] == 22` → TLS Record Type = Handshake
- `payload[1:3]` → TLS version (e.g., `0303` = TLS 1.2, `0304` = TLS 1.3)
- `payload[5]` → Handshake type (1 = ClientHello, 2 = ServerHello)

Returns strings like: `TLS_0303_HS_1` (TLS 1.2 ClientHello) or `"none"` if no TLS handshake found.

This is a simplified version of **JA3 fingerprinting** — useful for detecting malware using unusual TLS versions or identifying known-bad cipher suite patterns.

---

#### Complete Feature Vector Output
```python
{
    "connection_frequency": 20,        # int   — total packets in flow
    "avg_packet_size": 412.5,          # float — mean bytes per packet
    "entropy": 2.807,                  # float — Shannon entropy of size distribution
    "burst_rate": 7,                   # int   — number of rapid (<100ms) packet pairs
    "inter_arrival_time": 0.043,       # float — mean seconds between packets
    "tls_fingerprint": "TLS_0303_HS_1" # str   — TLS version + handshake type (or "none")
}
```

---

## Trigger Conditions Summary

| Trigger | Condition | Minimum Packets Required |
|---------|-----------|--------------------------|
| Flow full | `len(flow) >= 20` | 20 |
| Flow timeout | Idle for > 10 seconds | > 5 |

The 5-packet minimum on timeout prevents noise from single-packet flows (ARP, ICMP, SYN probes) producing meaningless feature vectors.

---

## Current Limitations and Planned Improvements

| Area | Current State | Planned |
|------|--------------|---------|
| Protocol coverage | TCP only | Add UDP, ICMP |
| Flow direction | Unidirectional (src→dst) | Bidirectional merging (src↔dst same key) |
| TLS fingerprinting | Version + handshake type only | Full JA3 fingerprint (cipher suites, extensions) |
| ML integration | Feature vector printed to stdout | Pass to scikit-learn / ONNX classifier |
| `utils.py` | Empty stub | Shared helpers (IP geolookup, port→service, …) |
| Persistence | In-memory only (lost on restart) | Write feature vectors to Kafka / database |
| Kafka integration | None | Publish feature vectors to `dpi.features` topic |

---

## How to Run

```bash
# Install dependencies (requires root for packet capture)
pip install scapy numpy

# Run (must be root to open raw sockets)
cd dpi_service
sudo python3 dpi_main.py
```

**Expected output while running:**
```
DPI STARTING...
Starting packet capture...
Using interface: eth0

FEATURE VECTOR:
{'connection_frequency': 20, 'avg_packet_size': 398.4, 'entropy': 2.91, ...}

FLOW TIMEOUT FEATURES:
{'connection_frequency': 8, 'avg_packet_size': 64.0, 'entropy': 0.0, ...}
```

---

## Relationship to the Rest of ACDS

```
Layer 4 (This branch)          →    Layer 5 (DPI Service)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
eBPF Agent (syscall-level)     →    Scapy (packet-level)
Kafka telemetry.raw            →    Kafka dpi.features (planned)
Per-process event metadata     →    Per-flow statistical features
React Dashboard visualization  →    ML Classifier → Threat Score
```

The two layers are **complementary, not redundant**:
- The eBPF telemetry tells you **which processes** made connections
- The DPI layer tells you **what the traffic looks like** (size, timing, TLS)
- Combined, they enable attribution: *"Process X made a connection that looks like C2 beaconing"*
