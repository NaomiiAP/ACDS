# ACDS Attack Simulation Guide

This document explains how the `simulate_attacks.py` script works, what features it triggers in the ACDS pipeline, and how it populates the Attack Graph.

## 1. Overview

The simulator is designed to bridge the gap between "normal traffic" (pings, curls) and "attack traffic" (scans, exfil). It specifically targets the features extracted by the **DPI Service** and the syscalls captured by the **Telemetry Agent**.

## 2. Attack Patterns

### 2.1 Port Scanning (Vertical)
- **Logic**: Iteratively attempts to connect to 50+ common ports on a single target IP.
- **ML Trigger**: High `window_unique_dst_ports` feature.
- **Risk Reason**: `port_scanning`.
- **Graph Effect**: Creates a `(:Process)` node connected to a single `(:IP)` node via multiple `SUSPICIOUS_CONNECTION` edges if the score is high enough.

### 2.2 Data Exfiltration
- **Logic**: Sends large (1450 byte) packets containing random data (`os.urandom`).
- **ML Trigger**: High `entropy`, `avg_packet_size`, and `burst_rate`.
- **Risk Reason**: `high_entropy`, `large_avg_packet_size`, `high_burst_rate`.
- **Graph Effect**: Increases the `risk_score` of the `(:Process)` and `(:IP)` nodes.

### 2.3 C2 Beaconing
- **Logic**: Connects to a target IP every 2 seconds for a fixed number of iterations.
- **ML Trigger**: Low `inter_arrival_time` (IAT) variance and specific frequency.
- **Risk Reason**: `c2_timing`.
- **Graph Effect**: Establishes a persistent link between a process and a remote C2 IP.

### 2.4 Lateral Movement (Horizontal Scan)
- **Logic**: Attempts to connect to a specific port (e.g., 22/SSH) across a range of internal IPs (192.168.1.x).
- **ML Trigger**: High `container_unique_dst_ips` and `process_connection_count`.
- **Risk Reason**: `lateral_movement`, `container_scanning`.
- **Graph Effect**: The `(:Process)` node will have multiple edges fan out to several `(:IP)` nodes.

## 3. Telemetry Integration

The script uses `setproctitle` and `/proc/self/comm` to rename itself during execution. This allows the ACDS Telemetry Agent to attribute the network activity to descriptive process names:

- `scanner_v1`
- `exfiltrator_v1`
- `backdoor_v1`
- `pivoter_v1`

In the **Attack Graph**, you will see these names appearing as nodes, making it easy to trace which "malware" is performing which action.

## 4. Usage Tips

1.  **Run with sudo**: eBPF needs root to see everything.
2.  **Run with all services**: Make sure Docker, Telemetry, DPI, Correlation, ML, and Graph services are all running.
3.  **Check the Graph**: Open the React UI and navigate to the "Attack Graph" tab. You should see nodes appearing in real-time as the simulator runs.
