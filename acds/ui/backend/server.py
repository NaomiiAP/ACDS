import asyncio
import json
import logging
import os
import time
from collections import deque, Counter
from contextlib import asynccontextmanager

from aiokafka import AIOKafkaConsumer
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TelemetryServer")

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC             = os.getenv("KAFKA_TOPIC", "telemetry.raw")
KAFKA_ENRICHED_TOPIC    = os.getenv("KAFKA_ENRICHED_TOPIC", "enriched.flows")
KAFKA_ML_ALERTS_TOPIC   = os.getenv("KAFKA_ML_ALERTS_TOPIC", "ml.alerts")
KAFKA_TRIAGE_TOPIC      = os.getenv("KAFKA_TRIAGE_TOPIC", "triage.results")
MAX_EVENTS              = 10000
MAX_THREATS             = 2000

# ── State ──────────────────────────────────────────────────────────────────────
event_buffer  = deque(maxlen=MAX_EVENTS)
threat_buffer = deque(maxlen=MAX_THREATS)  # enriched.flows events
ml_alert_buffer = deque(maxlen=2000)
triage_buffer   = deque(maxlen=1000)
active_connections:        list[WebSocket] = []
threat_connections:        list[WebSocket] = []
ml_connections:            list[WebSocket] = []
triage_connections:        list[WebSocket] = []

status = {
    "kafka_connected":          False,
    "enriched_kafka_connected": False,
    "last_event_ts":            0,
    "total_events":             0,
    "total_threats":            0,
    "total_ml_alerts":          0,
    "total_triage":             0,
}


# ── Kafka consumers ────────────────────────────────────────────────────────────

async def consume_telemetry():
    """Consume telemetry.raw → broadcast to /ws/telemetry."""
    consumer = AIOKafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="telemetry_ui_backend",
        auto_offset_reset="earliest",
    )
    while True:
        try:
            await consumer.start()
            logger.info(f"Telemetry consumer connected: {KAFKA_TOPIC}")
            status["kafka_connected"] = True

            async for msg in consumer:
                try:
                    event = json.loads(msg.value.decode("utf-8"))
                    event_buffer.append(event)
                    status["last_event_ts"] = int(time.time())
                    status["total_events"] += 1

                    event_str = json.dumps({"type": "event", "data": event})
                    for ws in list(active_connections):
                        try:
                            await ws.send_text(event_str)
                        except Exception:
                            pass
                except json.JSONDecodeError:
                    logger.error("Failed to parse telemetry message")

        except Exception as e:
            logger.error(f"Telemetry Kafka error: {e}. Retrying in 5s...")
            status["kafka_connected"] = False
            await asyncio.sleep(5)
        finally:
            await consumer.stop()


async def consume_enriched():
    """Consume enriched.flows → buffer and broadcast to /ws/threats."""
    consumer = AIOKafkaConsumer(
        KAFKA_ENRICHED_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="threats_ui_backend",
        auto_offset_reset="latest",
    )
    while True:
        try:
            await consumer.start()
            logger.info(f"Enriched consumer connected: {KAFKA_ENRICHED_TOPIC}")
            status["enriched_kafka_connected"] = True

            async for msg in consumer:
                try:
                    event = json.loads(msg.value.decode("utf-8"))
                    threat_buffer.append(event)
                    status["total_threats"] += 1

                    payload = json.dumps({"type": "threat", "data": event})
                    for ws in list(threat_connections):
                        try:
                            await ws.send_text(payload)
                        except Exception:
                            pass
                except json.JSONDecodeError:
                    logger.error("Failed to parse enriched message")

        except Exception as e:
            logger.error(f"Enriched Kafka error: {e}. Retrying in 5s...")
            status["enriched_kafka_connected"] = False
            await asyncio.sleep(5)
        finally:
            await consumer.stop()


async def consume_ml_alerts():
    """Consume ml.alerts → buffer and broadcast to /ws/ml-alerts."""
    consumer = AIOKafkaConsumer(
        KAFKA_ML_ALERTS_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="ml_alerts_ui_backend",
        auto_offset_reset="latest",
    )
    while True:
        try:
            await consumer.start()
            logger.info(f"ML alerts consumer connected: {KAFKA_ML_ALERTS_TOPIC}")
            status["ml_alerts_kafka_connected"] = True

            async for msg in consumer:
                try:
                    event = json.loads(msg.value.decode("utf-8"))
                    ml_alert_buffer.append(event)
                    status["total_ml_alerts"] += 1

                    payload = json.dumps({"type": "ml_alert", "data": event})
                    for ws in list(ml_connections):
                        try:
                            await ws.send_text(payload)
                        except Exception:
                            pass
                except json.JSONDecodeError:
                    logger.error("Failed to parse ML alert message")

        except Exception as e:
            logger.error(f"ML alerts Kafka error: {e}. Retrying in 5s...")
            status["ml_alerts_kafka_connected"] = False
            await asyncio.sleep(5)
        finally:
            await consumer.stop()


async def consume_triage():
    """Consume triage.results → buffer and broadcast to /ws/triage."""
    consumer = AIOKafkaConsumer(
        KAFKA_TRIAGE_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="triage_ui_backend",
        auto_offset_reset="latest",
    )
    while True:
        try:
            await consumer.start()
            logger.info(f"Triage consumer connected: {KAFKA_TRIAGE_TOPIC}")
            status["triage_kafka_connected"] = True

            async for msg in consumer:
                try:
                    event = json.loads(msg.value.decode("utf-8"))
                    triage_buffer.append(event)
                    status["total_triage"] += 1

                    payload = json.dumps({"type": "triage", "data": event})
                    for ws in list(triage_connections):
                        try:
                            await ws.send_text(payload)
                        except Exception:
                            pass
                except json.JSONDecodeError:
                    logger.error("Failed to parse triage message")

        except Exception as e:
            logger.error(f"Triage Kafka error: {e}. Retrying in 5s...")
            status["triage_kafka_connected"] = False
            await asyncio.sleep(5)
        finally:
            await consumer.stop()


@asynccontextmanager
async def lifespan(app: FastAPI):
    t1 = asyncio.create_task(consume_telemetry())
    t2 = asyncio.create_task(consume_enriched())
    t3 = asyncio.create_task(consume_ml_alerts())
    t4 = asyncio.create_task(consume_triage())
    yield
    t1.cancel()
    t2.cancel()
    t3.cancel()
    t4.cancel()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── REST API ───────────────────────────────────────────────────────────────────

@app.get("/api/status")
def get_status():
    return {
        **status,
        "total_ml_alerts": status.get("total_ml_alerts", 0),
        "total_triage": status.get("total_triage", 0),
    }


@app.get("/api/events")
def get_events(limit: int = 100):
    events = list(event_buffer)[-limit:]
    events.reverse()
    return events


@app.get("/api/stats")
def get_stats(window: str = "10s"):
    now = time.time()
    cnt = 0
    tcp_count = udp_count = 0
    hosts = set()
    containers = set()
    processes = Counter()

    for event in event_buffer:
        ts = event.get("timestamp", 0)
        if now - ts <= 10:
            cnt += 1
            protocol = str(event.get("protocol", "")).upper()
            if protocol in ("TCP", "6"):
                tcp_count += 1
            elif protocol in ("UDP", "17"):
                udp_count += 1
            if h := event.get("host_id"):
                hosts.add(h)
            if c := event.get("container_id"):
                containers.add(c)
            if p := event.get("process_name"):
                processes[p] += 1

    return {
        "events_per_sec":     cnt / 10 if cnt > 0 else 0,
        "tcp_count":          tcp_count,
        "udp_count":          udp_count,
        "unique_hosts":       len(hosts),
        "unique_containers":  len(containers),
        "top_processes":      processes.most_common(5),
    }


@app.get("/api/threats")
def get_threats(limit: int = 100, min_score: float = 0.0):
    """Return last N enriched flows, optionally filtered by minimum risk score."""
    threats = [t for t in list(threat_buffer) if t.get("risk_score", 0) >= min_score]
    threats = threats[-limit:]
    threats.reverse()
    return threats


@app.get("/api/threats/stats")
def get_threat_stats():
    """Summary stats for the threat dashboard."""
    threats = list(threat_buffer)
    if not threats:
        return {"total": 0, "high": 0, "medium": 0, "low": 0, "top_processes": []}

    counts = Counter(t.get("risk_level", "low") for t in threats)
    processes = Counter(t.get("process_name", "unknown") for t in threats
                        if t.get("risk_level") == "high")
    return {
        "total":         len(threats),
        "high":          counts.get("high", 0),
        "medium":        counts.get("medium", 0),
        "low":           counts.get("low", 0),
        "top_processes": processes.most_common(5),
    }


@app.get("/api/ml/alerts")
async def get_ml_alerts(limit: int = 100, min_score: float = 0.0):
    """Return recent ML alerts, optionally filtered by min ensemble score."""
    alerts = list(ml_alert_buffer)[-limit:]
    if min_score > 0:
        alerts = [a for a in alerts if a.get("ensemble_score", 0) >= min_score]
    return alerts


@app.get("/api/ml/stats")
async def get_ml_stats():
    """ML alert statistics."""
    alerts = list(ml_alert_buffer)
    total = len(alerts)
    high = sum(1 for a in alerts if a.get("risk_level") == "high")
    medium = sum(1 for a in alerts if a.get("risk_level") == "medium")
    low = sum(1 for a in alerts if a.get("risk_level") == "low")

    # Count by predicted label
    label_counts = {}
    for a in alerts:
        label = a.get("predicted_label", "unknown")
        label_counts[label] = label_counts.get(label, 0) + 1

    # Top risky processes
    process_scores = {}
    for a in alerts:
        proc = a.get("process_name", "unknown")
        score = a.get("ensemble_score", 0)
        if proc not in process_scores or score > process_scores[proc]:
            process_scores[proc] = score
    top_processes = sorted(process_scores.items(), key=lambda x: x[1], reverse=True)[:10]

    # Average ensemble score
    avg_score = sum(a.get("ensemble_score", 0) for a in alerts) / total if total else 0

    return {
        "total_alerts": total,
        "high": high, "medium": medium, "low": low,
        "label_counts": label_counts,
        "top_risky_processes": top_processes,
        "avg_ensemble_score": round(avg_score, 3),
    }


@app.get("/api/triage")
async def get_triage_results(limit: int = 50):
    """Return recent LLM triage results."""
    return list(triage_buffer)[-limit:]


@app.get("/api/triage/{alert_id}")
async def get_triage_by_alert(alert_id: str):
    """Get triage result for a specific alert."""
    for t in triage_buffer:
        if t.get("alert_id") == alert_id:
            return t
    return {"error": "not found"}


# ── WebSocket Routes ───────────────────────────────────────────────────────────

@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        for event in list(event_buffer)[-100:]:
            await websocket.send_text(json.dumps({"type": "event", "data": event}))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)


@app.websocket("/ws/threats")
async def websocket_threats(websocket: WebSocket):
    """WebSocket for real-time enriched flow / threat events."""
    await websocket.accept()
    threat_connections.append(websocket)
    try:
        # Send last 50 threats on connect
        for t in list(threat_buffer)[-50:]:
            await websocket.send_text(json.dumps({"type": "threat", "data": t}))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in threat_connections:
            threat_connections.remove(websocket)


@app.websocket("/ws/ml-alerts")
async def ws_ml_alerts(websocket: WebSocket):
    """WebSocket for real-time ML detection alerts."""
    await websocket.accept()
    ml_connections.append(websocket)
    try:
        # Send last 50 ML alerts on connect
        for a in list(ml_alert_buffer)[-50:]:
            await websocket.send_text(json.dumps({"type": "ml_alert", "data": a}))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in ml_connections:
            ml_connections.remove(websocket)


@app.websocket("/ws/triage")
async def ws_triage(websocket: WebSocket):
    """WebSocket for real-time LLM triage results."""
    await websocket.accept()
    triage_connections.append(websocket)
    try:
        # Send last 50 triage results on connect
        for t in list(triage_buffer)[-50:]:
            await websocket.send_text(json.dumps({"type": "triage", "data": t}))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in triage_connections:
            triage_connections.remove(websocket)
