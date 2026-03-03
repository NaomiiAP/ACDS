"""
correlation_main.py — Entry point for the ACDS Correlation Service (Layer 6)

Consumes:
  - telemetry.raw  → populates Active Connection Registry (TTL store)
  - dpi.features   → triggers correlation + risk scoring

Publishes:
  - enriched.flows → fully attributed, risk-scored flow events
"""
import asyncio
import json
import logging
import os
import signal
import sys
import time

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from state_store import registry
from flow_correlator import correlate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CORRELATION] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("correlation")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC_TELEMETRY  = "telemetry.raw"
TOPIC_DPI        = "dpi.features"
TOPIC_ENRICHED   = "enriched.flows"

# Shared Kafka producer (set in main)
_producer = None

CONNECT_SYSCALLS = {"tcp_connect", "connect", "tcp_syn", "udp_send", "udp_sendmsg"}


async def ingest_telemetry():
    """Consume telemetry.raw and populate the Active Connection Registry."""
    consumer = AIOKafkaConsumer(
        TOPIC_TELEMETRY,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="correlation_telemetry",
        auto_offset_reset="latest",  # Only care about new events for correlation
    )
    await consumer.start()
    log.info(f"Telemetry consumer started on {TOPIC_TELEMETRY}")

    try:
        async for msg in consumer:
            try:
                event = json.loads(msg.value.decode("utf-8"))

                # Only index events that represent outbound connections
                syscall = str(event.get("syscall", "")).lower()
                if syscall not in CONNECT_SYSCALLS and event.get("dst_ip"):
                    pass  # Still index if has dst_ip

                src_ip   = event.get("src_ip", "")
                src_port = int(event.get("src_port", 0))
                dst_ip   = event.get("dst_ip", "")
                dst_port = int(event.get("dst_port", 0))
                protocol = str(event.get("protocol", "TCP")).upper()

                if dst_ip:
                    registry.put(
                        src_ip, src_port, dst_ip, dst_port, protocol,
                        metadata={
                            "pid":          event.get("pid"),
                            "process_name": event.get("process_name"),
                            "container_id": event.get("container_id", ""),
                            "host_id":      event.get("host_id", ""),
                            "timestamp":    event.get("timestamp", time.time()),
                        }
                    )
            except Exception as e:
                log.warning(f"Telemetry ingest error: {e}")
    finally:
        await consumer.stop()


async def ingest_dpi():
    """Consume dpi.features, correlate, score, and publish to enriched.flows."""
    global _producer

    consumer = AIOKafkaConsumer(
        TOPIC_DPI,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="correlation_dpi",
        auto_offset_reset="latest",
    )
    await consumer.start()
    log.info(f"DPI consumer started on {TOPIC_DPI}")

    # Periodic registry cleanup
    last_cleanup = time.time()

    try:
        async for msg in consumer:
            try:
                dpi_event = json.loads(msg.value.decode("utf-8"))
                enriched  = correlate(dpi_event)
                level     = enriched.get("risk_level", "low")
                process   = enriched.get("process_name", "unknown")

                log.info(
                    f"[{level.upper():6}] score={enriched['risk_score']:.2f} "
                    f"proc={process} "
                    f"{enriched.get('src_ip')}→{enriched.get('dst_ip')}:{enriched.get('dst_port')}"
                )

                # Publish enriched event to enriched.flows
                if _producer:
                    await _producer.send(
                        TOPIC_ENRICHED,
                        json.dumps(enriched).encode("utf-8")
                    )

                # TTL cleanup every 30 seconds
                if time.time() - last_cleanup > 30:
                    removed = registry.cleanup()
                    if removed:
                        log.debug(f"Registry cleanup: removed {removed} expired entries")
                    last_cleanup = time.time()

            except Exception as e:
                log.warning(f"DPI correlation error: {e}")
    finally:
        await consumer.stop()


async def main():
    global _producer

    _producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    await _producer.start()
    log.info(f"Kafka producer ready → publishing to {TOPIC_ENRICHED}")

    print("=" * 65)
    print("  ACDS CORRELATION SERVICE  —  Layer 6")
    print(f"  Consuming: {TOPIC_TELEMETRY}, {TOPIC_DPI}")
    print(f"  Publishing: {TOPIC_ENRICHED}")
    print("=" * 65)

    try:
        await asyncio.gather(
            ingest_telemetry(),
            ingest_dpi(),
        )
    finally:
        await _producer.stop()


def shutdown(sig, frame):
    log.info("Shutting down correlation service...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    asyncio.run(main())
