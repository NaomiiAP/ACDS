"""
graph_main.py — Entry point for the ACDS Attack Graph Service

Consumes:
  - ml.alerts      → builds/updates the attack graph in Neo4j
  - triage.results → (optional) annotates graph edges with triage info

Background tasks:
  - Risk propagation every 30 seconds
  - TTL cleanup every 5 minutes
  - FastAPI server on port 8100
"""

import asyncio
import json
import logging
import os
import signal
import sys
import threading
import time

import uvicorn
from aiokafka import AIOKafkaConsumer

from acds.graph_service.neo4j_client import Neo4jClient
from acds.graph_service.graph_schema import build_graph_from_alert
from acds.graph_service.risk_propagation import propagate_risk, ttl_cleanup
from acds.graph_service.api import app as fastapi_app, set_neo4j_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [GRAPH] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("graph_service")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC_ML_ALERTS = "ml.alerts"
TOPIC_TRIAGE = "triage.results"
API_PORT = int(os.getenv("GRAPH_API_PORT", "8100"))

# ── Kafka consumers ─────────────────────────────────────────────────


async def ingest_ml_alerts(neo4j_client: Neo4jClient):
    """Consume ml.alerts and build the attack graph."""
    consumer = AIOKafkaConsumer(
        TOPIC_ML_ALERTS,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="graph_service",
        auto_offset_reset="latest",
    )
    await consumer.start()
    log.info("ML alerts consumer started on %s", TOPIC_ML_ALERTS)

    try:
        async for msg in consumer:
            try:
                alert = json.loads(msg.value.decode("utf-8"))
                ops = build_graph_from_alert(alert)

                for cypher, params in ops:
                    await neo4j_client.execute_write(cypher, params)

                ensemble = alert.get("ensemble_score", 0)
                dst = alert.get("dst_ip", "?")
                proc = alert.get("process_name", "?")
                log.info(
                    "Graph updated: proc=%s dst=%s score=%.2f (%d ops)",
                    proc, dst, float(ensemble), len(ops),
                )
            except Exception as e:
                log.warning("Error processing ml.alert: %s", e)
    finally:
        await consumer.stop()


async def ingest_triage_results(neo4j_client: Neo4jClient):
    """Optionally consume triage.results to annotate existing graph edges."""
    consumer = AIOKafkaConsumer(
        TOPIC_TRIAGE,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="graph_service_triage",
        auto_offset_reset="latest",
    )
    await consumer.start()
    log.info("Triage consumer started on %s", TOPIC_TRIAGE)

    try:
        async for msg in consumer:
            try:
                triage = json.loads(msg.value.decode("utf-8"))
                alert_id = triage.get("alert_id", "")
                verdict = triage.get("verdict", "unknown")
                confidence = float(triage.get("confidence", 0.0))

                if not alert_id:
                    continue

                # Annotate existing edges that carry this alert_id
                query = """
                MATCH ()-[r]->()
                WHERE r.alert_id = $alert_id
                SET r.triage_verdict = $verdict,
                    r.triage_confidence = $confidence
                RETURN count(r) AS updated
                """
                result = await neo4j_client.execute_write(query, {
                    "alert_id": alert_id,
                    "verdict": verdict,
                    "confidence": confidence,
                })
                updated = result[0]["updated"] if result else 0
                if updated:
                    log.info("Triage annotated %d edges for alert %s → %s", updated, alert_id, verdict)
            except Exception as e:
                log.warning("Error processing triage result: %s", e)
    finally:
        await consumer.stop()


# ── Background tasks ────────────────────────────────────────────────


async def risk_propagation_loop(neo4j_client: Neo4jClient):
    """Run risk propagation every 30 seconds."""
    while True:
        await asyncio.sleep(30)
        try:
            await propagate_risk(neo4j_client)
        except Exception as e:
            log.warning("Risk propagation error: %s", e)


async def ttl_cleanup_loop(neo4j_client: Neo4jClient):
    """Run TTL cleanup every 5 minutes."""
    while True:
        await asyncio.sleep(300)
        try:
            await ttl_cleanup(neo4j_client)
        except Exception as e:
            log.warning("TTL cleanup error: %s", e)


# ── API server (runs in a thread) ───────────────────────────────────


def start_api_server():
    """Run the FastAPI server in a daemon thread."""
    config = uvicorn.Config(
        fastapi_app,
        host="0.0.0.0",
        port=API_PORT,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    log.info("FastAPI server started on port %d", API_PORT)


# ── Main ────────────────────────────────────────────────────────────


async def main():
    neo4j_client = Neo4jClient()

    # Wait for Neo4j to be ready (retry with backoff)
    for attempt in range(1, 11):
        try:
            await neo4j_client.verify_connectivity()
            break
        except Exception as e:
            log.warning("Neo4j not ready (attempt %d/10): %s", attempt, e)
            await asyncio.sleep(min(attempt * 2, 10))
    else:
        log.error("Could not connect to Neo4j after 10 attempts — exiting")
        sys.exit(1)

    # Inject client into the API module
    set_neo4j_client(neo4j_client)

    # Start API server in background thread
    start_api_server()

    print("=" * 65)
    print("  ACDS ATTACK GRAPH SERVICE")
    print(f"  Consuming: {TOPIC_ML_ALERTS}, {TOPIC_TRIAGE}")
    print(f"  API:       http://0.0.0.0:{API_PORT}/api/graph/summary")
    print(f"  Neo4j:     bolt://localhost:7687")
    print("=" * 65)

    try:
        await asyncio.gather(
            ingest_ml_alerts(neo4j_client),
            ingest_triage_results(neo4j_client),
            risk_propagation_loop(neo4j_client),
            ttl_cleanup_loop(neo4j_client),
        )
    finally:
        await neo4j_client.close()


def shutdown(sig, frame):
    log.info("Shutting down graph service...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    asyncio.run(main())
