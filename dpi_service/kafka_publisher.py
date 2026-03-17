import json
import os
from confluent_kafka import Producer

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
DPI_TOPIC = "dpi.features"

_producer = None

def get_producer():
    global _producer
    if _producer is None:
        _producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})
    return _producer


def publish_features(flow_key, features: dict, timestamp: float):
    """
    Publishes a DPI feature vector to the dpi.features Kafka topic.

    flow_key format: (src_ip, src_port, dst_ip, dst_port, proto_int)
    """
    src_ip, src_port, dst_ip, dst_port, proto_int = flow_key

    protocol_map = {6: "TCP", 17: "UDP"}
    protocol = protocol_map.get(proto_int, str(proto_int))

    message = {
        "src_ip":   src_ip,
        "src_port": src_port,
        "dst_ip":   dst_ip,
        "dst_port": dst_port,
        "protocol": protocol,
        "timestamp": timestamp,
        **features,
    }

    try:
        p = get_producer()
        p.produce(DPI_TOPIC, json.dumps(message).encode("utf-8"))
        p.poll(0)  # Non-blocking delivery report
    except Exception as e:
        print(f"[kafka_publisher] Failed to publish: {e}")


def flush():
    """Call on shutdown to ensure all messages are delivered."""
    if _producer:
        _producer.flush(timeout=5)
