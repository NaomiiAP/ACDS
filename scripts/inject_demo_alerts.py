#!/usr/bin/env python3
"""
inject_demo_alerts.py — Inject realistic ML alerts directly into Kafka.

This bypasses the ML model inference entirely and pushes pre-crafted
attack alert events into the `ml.alerts` topic.  These alerts will:
  1. Show up on the ML Detection page in real time
  2. Be consumed by the Graph Service to build the Attack Graph
  3. Be consumed by the LLM Triage service for explanation

Usage (run from WSL2 project root):
    python3 scripts/inject_demo_alerts.py

Or from Windows PowerShell (if confluent-kafka is installed):
    python scripts/inject_demo_alerts.py
"""

import json
import time
import uuid
import random
import sys
import os

# ── Configuration ───────────────────────────────────────────────────
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC_ML_ALERTS = "ml.alerts"
TOPIC_ENRICHED = "enriched.flows"

# ── Attack Scenario Templates ───────────────────────────────────────

ATTACK_SCENARIOS = [
    {
        "name": "Port Scanner",
        "process_name": "scanner_bolt",
        "pid": 31337,
        "src_ip": "192.168.1.50",
        "dst_ips": ["10.0.0.1", "10.0.0.2", "10.0.0.3", "10.0.0.5", "10.0.0.10"],
        "dst_ports": [22, 23, 80, 443, 3389, 8080, 8443, 4444, 1337, 31337],
        "protocol": "TCP",
        "ensemble_range": (0.70, 0.92),
        "label": "PortScan",
        "risk_reasons": ["port_scanning", "high_connection_volume", "lateral_movement"],
        "features": {
            "connection_frequency": 85,
            "avg_packet_size": 64,
            "entropy": 1.2,
            "burst_rate": 0.95,
            "inter_arrival_time": 0.005,
            "window_unique_dst_ports": 25,
            "process_connection_count": 50,
            "container_unique_dst_ips": 12,
        },
    },
    {
        "name": "Data Exfiltrator",
        "process_name": "exfiltrator_prime",
        "pid": 6666,
        "src_ip": "192.168.1.100",
        "dst_ips": ["185.220.101.42"],
        "dst_ports": [443, 8443],
        "protocol": "TCP",
        "ensemble_range": (0.82, 0.97),
        "label": "Exfiltration",
        "risk_reasons": ["high_entropy", "high_burst_rate", "anomalous_pattern"],
        "features": {
            "connection_frequency": 12,
            "avg_packet_size": 1460,
            "entropy": 7.8,
            "burst_rate": 0.92,
            "inter_arrival_time": 0.02,
            "window_unique_dst_ports": 2,
            "process_connection_count": 8,
            "container_unique_dst_ips": 1,
        },
    },
    {
        "name": "C2 Beacon",
        "process_name": "svchost_update",
        "pid": 4444,
        "src_ip": "192.168.1.75",
        "dst_ips": ["104.21.45.67"],
        "dst_ports": [80, 443],
        "protocol": "TCP",
        "ensemble_range": (0.68, 0.85),
        "label": "C2",
        "risk_reasons": ["c2_timing", "anomalous_pattern", "ensemble_threshold_exceeded"],
        "features": {
            "connection_frequency": 5,
            "avg_packet_size": 128,
            "entropy": 5.5,
            "burst_rate": 0.1,
            "inter_arrival_time": 0.002,
            "window_unique_dst_ports": 2,
            "process_connection_count": 25,
            "container_unique_dst_ips": 1,
        },
    },
    {
        "name": "Lateral Mover",
        "process_name": "pivoter_tool",
        "pid": 9999,
        "src_ip": "192.168.1.200",
        "dst_ips": ["192.168.1.10", "192.168.1.11", "192.168.1.12", "192.168.1.20", "192.168.1.30", "192.168.1.40"],
        "dst_ports": [22, 445, 3389],
        "protocol": "TCP",
        "ensemble_range": (0.72, 0.90),
        "label": "Infiltration",
        "risk_reasons": ["lateral_movement", "container_scanning", "high_connection_volume"],
        "features": {
            "connection_frequency": 40,
            "avg_packet_size": 256,
            "entropy": 3.8,
            "burst_rate": 0.7,
            "inter_arrival_time": 0.05,
            "window_unique_dst_ports": 5,
            "process_connection_count": 35,
            "container_unique_dst_ips": 15,
        },
    },
    {
        "name": "DDoS Botnet",
        "process_name": "httpflood",
        "pid": 7777,
        "src_ip": "192.168.1.150",
        "dst_ips": ["203.0.113.50"],
        "dst_ports": [80, 443],
        "protocol": "TCP",
        "ensemble_range": (0.88, 0.99),
        "label": "DDoS",
        "risk_reasons": ["high_burst_rate", "high_connection_volume", "anomalous_pattern"],
        "features": {
            "connection_frequency": 200,
            "avg_packet_size": 512,
            "entropy": 2.1,
            "burst_rate": 0.99,
            "inter_arrival_time": 0.001,
            "window_unique_dst_ports": 2,
            "process_connection_count": 100,
            "container_unique_dst_ips": 1,
        },
    },
    {
        "name": "SSH Brute Force",
        "process_name": "hydra",
        "pid": 5555,
        "src_ip": "192.168.1.80",
        "dst_ips": ["10.0.0.50"],
        "dst_ports": [22],
        "protocol": "TCP",
        "ensemble_range": (0.75, 0.88),
        "label": "BruteForce",
        "risk_reasons": ["high_connection_volume", "c2_timing", "lateral_movement"],
        "features": {
            "connection_frequency": 150,
            "avg_packet_size": 96,
            "entropy": 4.2,
            "burst_rate": 0.85,
            "inter_arrival_time": 0.01,
            "window_unique_dst_ports": 1,
            "process_connection_count": 60,
            "container_unique_dst_ips": 1,
        },
    },
]


def _jitter(value, pct=0.15):
    """Add random jitter to a numeric value."""
    return value * (1 + random.uniform(-pct, pct))


def build_alert(scenario, dst_ip=None, dst_port=None):
    """Create a single ML alert event from a scenario template."""
    ts = time.time()
    ensemble = random.uniform(*scenario["ensemble_range"])
    supervised = ensemble * random.uniform(0.85, 1.05)
    unsupervised = ensemble * random.uniform(0.75, 1.1)

    if ensemble >= 0.85:
        risk_level = "critical"
    elif ensemble >= 0.70:
        risk_level = "high"
    elif ensemble >= 0.50:
        risk_level = "medium"
    else:
        risk_level = "low"

    chosen_dst_ip = dst_ip or random.choice(scenario["dst_ips"])
    chosen_dst_port = dst_port or random.choice(scenario["dst_ports"])

    features = {k: round(_jitter(v), 4) if isinstance(v, (int, float)) else v
                for k, v in scenario["features"].items()}

    # Add window features
    features.update({
        "tls_fingerprint_encoded": 0.0,
        "window_10s_count": random.randint(3, 30),
        "window_30s_count": random.randint(10, 80),
        "window_60s_count": random.randint(20, 150),
        "window_avg_entropy": features.get("entropy", 3.0) * 0.9,
        "window_max_burst": features.get("burst_rate", 0.5) * 1.2,
    })

    alert = {
        "alert_id": str(uuid.uuid4()),
        "flow_id": f"{scenario['src_ip']}:{random.randint(40000,65000)}->{chosen_dst_ip}:{chosen_dst_port}",
        "timestamp": ts,
        "src_ip": scenario["src_ip"],
        "dst_ip": chosen_dst_ip,
        "src_port": random.randint(40000, 65000),
        "dst_port": chosen_dst_port,
        "protocol": scenario["protocol"],
        "process_name": scenario["process_name"],
        "pid": scenario["pid"],
        "container_id": "",
        "host_id": "DESKTOP-GNIKQ6E",
        "supervised_score": round(min(supervised, 1.0), 4),
        "unsupervised_score": round(min(unsupervised, 1.0), 4),
        "ensemble_score": round(ensemble, 4),
        "predicted_label": scenario["label"],
        "risk_level": risk_level,
        "model_version": "v1.0-onnx",
        "features": features,
        "risk_reasons": scenario["risk_reasons"],
        "enriched_flow": {
            "src_ip": scenario["src_ip"],
            "dst_ip": chosen_dst_ip,
            "dst_port": chosen_dst_port,
            "protocol": scenario["protocol"],
            "process_name": scenario["process_name"],
            "pid": scenario["pid"],
            "host_id": "DESKTOP-GNIKQ6E",
            "risk_score": round(ensemble, 3),
            "risk_level": risk_level,
            "timestamp": ts,
        },
    }
    return alert


def main():
    try:
        from confluent_kafka import Producer
    except ImportError:
        print("[!] 'confluent-kafka' is not installed.")
        print("[!] Install it with: pip install confluent-kafka")
        sys.exit(1)

    producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP})

    def delivery_cb(err, msg):
        if err:
            print(f"  [X] Delivery failed: {err}")

    print("=" * 60)
    print("  ACDS DEMO ALERT INJECTOR")
    print(f"  Kafka: {KAFKA_BOOTSTRAP}")
    print(f"  Topic: {TOPIC_ML_ALERTS}")
    print(f"  Scenarios: {len(ATTACK_SCENARIOS)}")
    print("=" * 60)
    print()

    total_injected = 0

    # Run 3 rounds of all scenarios
    for round_num in range(1, 4):
        print(f"-- Round {round_num}/3 -------------------------------------")
        for scenario in ATTACK_SCENARIOS:
            # Generate 2-4 alerts per scenario per round
            num_alerts = random.randint(2, 4)
            for _ in range(num_alerts):
                alert = build_alert(scenario)
                payload = json.dumps(alert).encode("utf-8")

                producer.produce(
                    TOPIC_ML_ALERTS,
                    value=payload,
                    callback=delivery_cb,
                )
                total_injected += 1

                risk = alert["risk_level"].upper()
                score = alert["ensemble_score"]
                proc = alert["process_name"]
                dst = alert["dst_ip"]
                print(f"  [{risk:8}] score={score:.3f}  proc={proc:<20}  dst={dst}")

            producer.flush()
            time.sleep(0.3)

        print()
        time.sleep(1)

    producer.flush()
    print(f"[OK] Injected {total_injected} alerts into '{TOPIC_ML_ALERTS}'")
    print()
    print("Now check your dashboard:")
    print("  -> ML Detection page: http://localhost:5173")
    print("  -> Attack Graph page: http://localhost:5173")
    print("  -> Kafka Monitor should show alerts scrolling")


if __name__ == "__main__":
    main()
