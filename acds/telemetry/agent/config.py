import os
import socket

# Schema definitions
SCHEMA_VERSION = "1.0"

# Kafka settings
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "telemetry.raw")
KAFKA_CONFIG = {
    'bootstrap.servers': KAFKA_BROKER,
    'acks': 'all',
    'retries': 3,
    'linger.ms': 1, # Stream immediately
    'batch.num.messages': 1
}

# Host identification
def get_host_id():
    # Will use environment variable if set to override hostname
    if "HOST_ID" in os.environ:
        return os.environ["HOST_ID"]
    try:
        return socket.gethostname()
    except Exception:
        return "unknown_host"

HOST_ID = get_host_id()
