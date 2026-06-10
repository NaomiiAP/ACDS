"""
llm_main.py — Entry point for the ACDS LLM Triage Service

Consumes:
  - ml.alerts  → alerts scored by the ML ensemble pipeline

Publishes:
  - triage.results → LLM-generated triage analysis for high-scoring alerts
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
import uuid
from dotenv import load_dotenv

# Load .env file at startup
load_dotenv()

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from acds.llm_service.groq_client import GroqClient
from acds.llm_service.prompt_templates import build_prompt
from acds.llm_service.triage_formatter import parse_llm_output

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [LLM-TRIAGE] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("llm_triage")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC_ML_ALERTS = "ml.alerts"
TOPIC_TRIAGE = "triage.results"
ENSEMBLE_THRESHOLD = 0.5
# Auto-triage is off by default — use the UI "Run AI Triage" button per alert instead.
AUTO_TRIAGE = os.getenv("AUTO_TRIAGE", "false").lower() in ("1", "true", "yes")

# Shared Kafka producer (set in main)
_producer = None
_llm = None


async def ingest_alerts():
    """Consume ml.alerts, triage qualifying alerts via LLM, publish results."""
    global _producer, _llm

    consumer = AIOKafkaConsumer(
        TOPIC_ML_ALERTS,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="llm_triage_groq_v1",
        auto_offset_reset="latest",
    )
    await consumer.start()
    log.info("Consumer started on %s", TOPIC_ML_ALERTS)

    try:
        async for msg in consumer:
            try:
                alert = json.loads(msg.value.decode("utf-8"))

                # Only process alerts meeting the ensemble score threshold
                ensemble_score = float(alert.get("ensemble_score", 0))
                if ensemble_score < ENSEMBLE_THRESHOLD:
                    continue

                alert_id = alert.get("alert_id", str(uuid.uuid4()))
                log.info(
                    "Processing alert %s (ensemble_score=%.2f)",
                    alert_id, ensemble_score,
                )

                # Build prompt and call LLM
                start_ms = time.time()
                prompt = build_prompt(alert)

                try:
                    raw_output = await _llm.generate(prompt)
                except Exception as exc:
                    log.error("LLM generation failed for alert %s: %s", alert_id, exc)
                    raw_output = ""

                processing_time_ms = int((time.time() - start_ms) * 1000)

                # Parse structured fields from LLM response
                parsed = parse_llm_output(raw_output)

                # Build triage result message
                triage_result = {
                    "triage_id": str(uuid.uuid4()),
                    "alert_id": alert_id,
                    "timestamp": time.time(),
                    "explanation": parsed["explanation"],
                    "attack_stage": parsed["attack_stage"],
                    "confidence": parsed["confidence"],
                    "severity": parsed["severity"],
                    "mitigation_steps": parsed["mitigation_steps"],
                    "model_used": _llm.model,
                    "advisory_only": True,
                    "processing_time_ms": processing_time_ms,
                    "raw_llm_output": raw_output,
                    "alert_context": {
                        "ensemble_score": ensemble_score,
                        "predicted_label": alert.get("predicted_label"),
                        "risk_level": alert.get("risk_level"),
                        "src_ip": alert.get("src_ip"),
                        "dst_ip": alert.get("dst_ip"),
                        "dst_port": alert.get("dst_port"),
                        "process_name": alert.get("process_name"),
                    },
                }

                log.info(
                    "Triage complete for %s — stage=%s severity=%s confidence=%s (%dms)",
                    alert_id,
                    parsed["attack_stage"],
                    parsed["severity"],
                    parsed["confidence"],
                    processing_time_ms,
                )

                # Publish to triage.results
                if _producer:
                    await _producer.send(
                        TOPIC_TRIAGE,
                        json.dumps(triage_result).encode("utf-8"),
                    )

            except Exception as exc:
                log.warning("Alert processing error: %s", exc)
    finally:
        await consumer.stop()


async def main():
    global _producer, _llm

    _llm = GroqClient()
    _producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    await _producer.start()
    log.info("Kafka producer ready -> publishing to %s", TOPIC_TRIAGE)

    # Check Groq availability at startup
    available = await _llm.is_available()
    if available:
        log.info("Groq API is configured (model: %s)", _llm.model)
    else:
        log.warning("Groq API key is NOT found in environment!")

    print("=" * 65)
    print("  ACDS GROQ TRIAGE SERVICE")
    print(f"  Consuming:  {TOPIC_ML_ALERTS}")
    print(f"  Publishing: {TOPIC_TRIAGE}")
    print(f"  Model:      {_llm.model}")
    print(f"  Threshold:  ensemble_score >= {ENSEMBLE_THRESHOLD}")
    print(f"  Auto-triage: {'ON' if AUTO_TRIAGE else 'OFF (use UI button per alert)'}")
    print("=" * 65)

    try:
        if AUTO_TRIAGE:
            await ingest_alerts()
        else:
            log.info(
                "Auto-triage disabled. Triage runs on-demand via UI "
                "(POST /api/triage/request/{alert_id})."
            )
            while True:
                await asyncio.sleep(3600)
    finally:
        await _producer.stop()
        await _llm.close()


def shutdown(sig, frame):
    log.info("Shutting down LLM triage service...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    asyncio.run(main())
