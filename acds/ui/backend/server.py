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
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "telemetry.raw")
MAX_EVENTS = 10000

# State
event_buffer = deque(maxlen=MAX_EVENTS)
active_connections: list[WebSocket] = []
status = {
    "kafka_connected": False,
    "last_event_ts": 0,
    "total_events": 0
}

async def consume_kafka():
    consumer = AIOKafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="telemetry_ui_backend",
        auto_offset_reset="earliest",
    )
    
    while True:
        try:
            await consumer.start()
            logger.info(f"Connected to Kafka at {KAFKA_BOOTSTRAP_SERVERS}")
            status["kafka_connected"] = True
            
            async for msg in consumer:
                try:
                    event = json.loads(msg.value.decode('utf-8'))
                    # Keep schema EXACTLY as sent by Python/C agent
                    event_buffer.append(event)
                    
                    status["last_event_ts"] = int(time.time())
                    status["total_events"] += 1
                    
                    # Broadcast
                    event_str = json.dumps({"type": "event", "data": event})
                    for connection in active_connections:
                        try:
                            await connection.send_text(event_str)
                        except Exception:
                            pass # Disconnects are handled in the route
                            
                except json.JSONDecodeError:
                    logger.error("Failed to parse Kafka message")
                    
        except Exception as e:
            logger.error(f"Kafka consumer error: {e}. Retrying in 5 seconds...")
            status["kafka_connected"] = False
            await asyncio.sleep(5)
        finally:
            await consumer.stop()

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(consume_kafka())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/status")
def get_status():
    return status

@app.get("/api/events")
def get_events(limit: int = 100):
    # Return last N events
    events = list(event_buffer)[-limit:]
    events.reverse() # Newest first
    return events

@app.get("/api/stats")
def get_stats(window: str = "10s"):
    now = time.time()
    events_per_sec = 0
    tcp_count = 0
    udp_count = 0
    hosts = set()
    containers = set()
    processes = Counter()

    for event in event_buffer:
        # Check window
        ts = event.get("timestamp", 0)
        if now - ts <= 10:
            events_per_sec += 1
            protocol = str(event.get("protocol", "")).upper()
            if protocol == "TCP" or protocol == "6":
                tcp_count += 1
            elif protocol == "UDP" or protocol == "17":
                udp_count += 1
                
            if h := event.get("host_id"):
                hosts.add(h)
            if c := event.get("container_id"):
                containers.add(c)
            if p := event.get("process_name"):
                processes[p] += 1
                
    return {
        "events_per_sec": events_per_sec / 10 if events_per_sec > 0 else 0,
        "tcp_count": tcp_count,
        "udp_count": udp_count,
        "unique_hosts": len(hosts),
        "unique_containers": len(containers),
        "top_processes": processes.most_common(5)
    }

@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        # Send initial batch of last 100 events to quickly populate the UI
        initial_events = list(event_buffer)[-100:]
        for event in initial_events:
            await websocket.send_text(json.dumps({"type": "event", "data": event}))
            
        while True:
            # Keep connection alive, listen for control messages like {"type": "pause"}
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                # Filtering logic or pausing can be implemented here if client needs it.
                # For this MVP, we just accept messages.
                pass
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        active_connections.remove(websocket)
