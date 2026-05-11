<<<<<<< HEAD
import signal
import sys
import time
from packet_capture import start_capture
from flow_manager import add_packet, flows, get_expired_flows
from feature_extractor import extract_features
from kafka_publisher import publish_features, flush

FLOW_LIMIT = 20   # packets before extracting from active flow


def process_packet(packet):
    key = add_packet(packet)
    if key is None:
        return

    # Trigger 1 — Flow is full (reached FLOW_LIMIT packets)
    if len(flows[key]) >= FLOW_LIMIT:
        features = extract_features(flows[key])
        ts = time.time()
        publish_features(key, features, ts)
        print(f"[DPI] FLOW FULL  → published features for {key[0]}:{key[1]} ↔ {key[2]}:{key[3]}")
        flows[key] = []  # Reset flow buffer, keep tracking

    # Trigger 2 — Timeout check for idle flows
    expired = get_expired_flows()
    for exp_key in expired:
        if exp_key in flows and len(flows[exp_key]) > 5:
            features = extract_features(flows[exp_key])
            ts = time.time()
            publish_features(exp_key, features, ts)
            print(f"[DPI] TIMEOUT   → published features for {exp_key[0]}:{exp_key[1]} ↔ {exp_key[2]}:{exp_key[3]}")
        flows.pop(exp_key, None)


def shutdown(sig, frame):
    print("\n[DPI] Shutting down, flushing Kafka producer...")
    flush()
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    print("=" * 60)
    print("  ACDS DPI SERVICE  —  Layer 5")
    print("  Capture: TCP + UDP | Bidirectional flows | Kafka→dpi.features")
    print("=" * 60)
=======
from packet_capture import start_capture
from flow_manager import add_packet, flows, get_expired_flows
from feature_extractor import extract_features

FLOW_LIMIT = 20


def process_packet(packet):

    key = add_packet(packet)

    if key is None:
        return

    if len(flows[key]) >= FLOW_LIMIT:

        features = extract_features(flows[key])

        print("\nFEATURE VECTOR:")
        print(features)

        flows[key] = []

    expired = get_expired_flows()

    for exp_key in expired:

        if exp_key in flows and len(flows[exp_key]) > 5:

            features = extract_features(flows[exp_key])

            print("\nFLOW TIMEOUT FEATURES:")
            print(features)

        flows.pop(exp_key, None)


if __name__ == "__main__":
    print("DPI STARTING...")
>>>>>>> 249fcebef8fc6fb9b6ee6caf55a4990337cf304a
    start_capture(process_packet)