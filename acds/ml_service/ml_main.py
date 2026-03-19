"""
ml_main.py — Entry point for the ACDS ML Detection Service.

Consumes:
    enriched.flows  -> enriched, attributed flow events from the correlation service

Publishes:
    ml.alerts       -> ML-scored alert events when ensemble_score >= threshold

Follows the same async Kafka pattern as correlation_main.py.
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
import uuid
from typing import Any, Dict, Optional

import numpy as np
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from ml_service.feature_pipeline import FeaturePipeline
from ml_service.inference.onnx_runner import ONNXRunner
from ml_service.inference.threshold_manager import ThresholdManager
from ml_service.models.ensemble import EnsembleModel
from ml_service.registry.model_registry import ModelRegistry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ML-DETECT] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ml_service")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC_ENRICHED = "enriched.flows"
TOPIC_ML_ALERTS = "ml.alerts"
ONNX_MODEL_DIR = os.getenv("ML_ONNX_MODEL_DIR", os.path.join(os.path.dirname(__file__), "onnx_models"))

# Shared Kafka producer (set in main)
_producer: Optional[AIOKafkaProducer] = None

# Feature ordering for the 14-element vector
FEATURE_ORDER = [
    "connection_frequency",
    "avg_packet_size",
    "entropy",
    "burst_rate",
    "inter_arrival_time",
    "tls_fingerprint_encoded",
    "window_10s_count",
    "window_30s_count",
    "window_60s_count",
    "window_avg_entropy",
    "window_max_burst",
    "window_unique_dst_ports",
    "process_connection_count",
    "container_unique_dst_ips",
]


def _build_risk_reasons(features: Dict[str, float], scores: Dict[str, Any]) -> list:
    """Determine human-readable risk reasons from features and scores."""
    reasons = []

    if features.get("entropy", 0) > 5.0:
        reasons.append("high_entropy")
    if features.get("burst_rate", 0) > 0.8:
        reasons.append("high_burst_rate")
    if features.get("inter_arrival_time", 0) < 0.01:
        reasons.append("c2_timing")
    if features.get("window_60s_count", 0) > 50:
        reasons.append("high_connection_volume")
    if features.get("process_connection_count", 0) > 20:
        reasons.append("lateral_movement")
    if features.get("container_unique_dst_ips", 0) > 10:
        reasons.append("container_scanning")
    if features.get("window_unique_dst_ports", 0) > 15:
        reasons.append("port_scanning")
    if scores.get("unsupervised_score", 0) > 0.7:
        reasons.append("anomalous_pattern")

    return reasons if reasons else ["ensemble_threshold_exceeded"]


def _features_to_array(features: Dict[str, float]) -> np.ndarray:
    """Convert feature dict to (1, 14) float32 array."""
    vec = [features.get(name, 0.0) for name in FEATURE_ORDER]
    return np.array([vec], dtype=np.float32)


async def ingest_enriched_flows(
    pipeline: FeaturePipeline,
    runner: ONNXRunner,
    ensemble: EnsembleModel,
    threshold_mgr: ThresholdManager,
    registry: ModelRegistry,
):
    """Consume enriched.flows, run ML inference, produce ml.alerts."""
    global _producer

    consumer = AIOKafkaConsumer(
        TOPIC_ENRICHED,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="ml_detection_service",
        auto_offset_reset="latest",
    )
    await consumer.start()
    log.info("Consumer started on %s", TOPIC_ENRICHED)

    last_cleanup = time.time()

    try:
        async for msg in consumer:
            try:
                enriched_flow = json.loads(msg.value.decode("utf-8"))

                # 1. Add to feature pipeline time windows
                pipeline.add_flow(enriched_flow)

                # 2. Compute aggregate features
                features = pipeline.compute_features(enriched_flow)
                X = _features_to_array(features)

                # 3. Run ONNX inference for each model
                xgb_score = 0.5
                rf_score = 0.5
                ae_score = 0.5
                iforest_score = 0.5

                if runner.is_loaded("xgboost"):
                    try:
                        xgb_score = float(runner.predict("xgboost", X)[0])
                    except Exception as e:
                        log.debug("XGBoost inference error: %s", e)

                if runner.is_loaded("random_forest"):
                    try:
                        rf_score = float(runner.predict("random_forest", X)[0])
                    except Exception as e:
                        log.debug("RF inference error: %s", e)

                if runner.is_loaded("autoencoder"):
                    try:
                        ae_score = float(runner.predict_autoencoder_score("autoencoder", X)[0])
                    except Exception as e:
                        log.debug("Autoencoder inference error: %s", e)

                if runner.is_loaded("isolation_forest"):
                    try:
                        iforest_score = float(runner.predict("isolation_forest", X)[0])
                    except Exception as e:
                        log.debug("IForest inference error: %s", e)

                # 4. Ensemble scoring
                result = ensemble.predict(xgb_score, rf_score, ae_score, iforest_score)
                ens_score = result["ensemble_score"]

                # Track score for dynamic threshold
                threshold_mgr.add_score(ens_score)

                # 5. Produce alert if above threshold
                if threshold_mgr.should_alert(ens_score):
                    active = registry.get_active()
                    model_version = active["version"] if active else "unknown"

                    risk_level = threshold_mgr.get_risk_level(ens_score)
                    risk_reasons = _build_risk_reasons(features, result)

                    alert = {
                        "alert_id": str(uuid.uuid4()),
                        "flow_id": (
                            f"{enriched_flow.get('src_ip', '?')}:{enriched_flow.get('src_port', '?')}"
                            f"->{enriched_flow.get('dst_ip', '?')}:{enriched_flow.get('dst_port', '?')}"
                        ),
                        "timestamp": time.time(),
                        "src_ip": enriched_flow.get("src_ip", ""),
                        "dst_ip": enriched_flow.get("dst_ip", ""),
                        "src_port": enriched_flow.get("src_port", 0),
                        "dst_port": enriched_flow.get("dst_port", 0),
                        "protocol": enriched_flow.get("protocol", "TCP"),
                        "process_name": enriched_flow.get("process_name", "unknown"),
                        "container_id": enriched_flow.get("container_id", ""),
                        "host_id": enriched_flow.get("host_id", ""),
                        "supervised_score": result["supervised_score"],
                        "unsupervised_score": result["unsupervised_score"],
                        "ensemble_score": ens_score,
                        "predicted_label": result["predicted_label"],
                        "risk_level": risk_level,
                        "model_version": model_version,
                        "features": features,
                        "risk_reasons": risk_reasons,
                        "enriched_flow": enriched_flow,
                    }

                    log.info(
                        "[%s] ensemble=%.3f label=%s proc=%s %s->%s:%s reasons=%s",
                        risk_level.upper(),
                        ens_score,
                        result["predicted_label"],
                        enriched_flow.get("process_name", "?"),
                        enriched_flow.get("src_ip", "?"),
                        enriched_flow.get("dst_ip", "?"),
                        enriched_flow.get("dst_port", "?"),
                        risk_reasons,
                    )

                    if _producer:
                        await _producer.send(
                            TOPIC_ML_ALERTS,
                            json.dumps(alert).encode("utf-8"),
                        )

                # Periodic pipeline cleanup
                if time.time() - last_cleanup > 30:
                    removed = pipeline.cleanup()
                    if removed:
                        log.debug("Pipeline cleanup: removed %d stale keys", removed)
                    last_cleanup = time.time()

            except Exception as e:
                log.warning("Flow processing error: %s", e)
    finally:
        await consumer.stop()


def _load_onnx_models(runner: ONNXRunner) -> None:
    """Attempt to load all four ONNX models from the model directory."""
    model_files = {
        "xgboost": "xgboost.onnx",
        "random_forest": "random_forest.onnx",
        "autoencoder": "autoencoder.onnx",
        "isolation_forest": "isolation_forest.onnx",
    }
    for name, filename in model_files.items():
        path = os.path.join(ONNX_MODEL_DIR, filename)
        if os.path.exists(path):
            try:
                runner.load_model(name, path)
            except Exception as e:
                log.warning("Failed to load %s: %s", filename, e)
        else:
            log.info("ONNX model not found (will use fallback): %s", path)


async def main():
    global _producer

    _producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    await _producer.start()
    log.info("Kafka producer ready -> publishing to %s", TOPIC_ML_ALERTS)

    # Initialize components
    pipeline = FeaturePipeline()
    runner = ONNXRunner()
    ensemble = EnsembleModel()
    threshold_mgr = ThresholdManager()
    registry = ModelRegistry()

    # Load ONNX models
    _load_onnx_models(runner)

    print("=" * 65)
    print("  ACDS ML DETECTION SERVICE")
    print(f"  Consuming: {TOPIC_ENRICHED}")
    print(f"  Publishing: {TOPIC_ML_ALERTS}")
    print(f"  Loaded models: {runner.list_models()}")
    print(f"  Threshold: {threshold_mgr.threshold:.4f}")
    print("=" * 65)

    try:
        await ingest_enriched_flows(pipeline, runner, ensemble, threshold_mgr, registry)
    finally:
        await _producer.stop()


def shutdown(sig, frame):
    log.info("Shutting down ML detection service...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    asyncio.run(main())
