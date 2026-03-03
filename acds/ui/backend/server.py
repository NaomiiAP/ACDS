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
MAX_EVENTS              = 10000
MAX_THREATS             = 2000

# ── State ──────────────────────────────────────────────────────────────────────
event_buffer  = deque(maxlen=MAX_EVENTS)
threat_buffer = deque(maxlen=MAX_THREATS)  # enriched.flows events
active_connections:        list[WebSocket] = []
threat_connections:        list[WebSocket] = []

status = {
    "kafka_connected":          False,
    "enriched_kafka_connected": False,
    "last_event_ts":            0,
    "total_events":             0,
    "total_threats":            0,
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    t1 = asyncio.create_task(consume_telemetry())
    t2 = asyncio.create_task(consume_enriched())
    yield
    t1.cancel()
    t2.cancel()


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
    return status


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
