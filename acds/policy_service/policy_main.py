"""
policy_main.py — ACDS Response & Policy Engine

Consumes:
  - ml.alerts       → evaluate YAML rules → policy.actions
  - policy.commands → human approve/reject from UI

Publishes:
  - policy.actions  → backend UI + audit trail

API: http://0.0.0.0:8200
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
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from acds.policy_service.action_store import ActionStore
from acds.policy_service.api import app as fastapi_app, init_api
from acds.policy_service.enforcer import execute
from acds.policy_service.rule_engine import RuleEngine

logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s [POLICY] %(message)s",
  datefmt="%H:%M:%S",
)
log = logging.getLogger("policy_service")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC_ML_ALERTS = "ml.alerts"
TOPIC_ACTIONS = "policy.actions"
TOPIC_COMMANDS = "policy.commands"
API_PORT = int(os.getenv("POLICY_API_PORT", "8200"))

store = ActionStore()
engine = RuleEngine()
_producer: AIOKafkaProducer | None = None


async def publish_action(action: dict) -> None:
  global _producer
  if _producer is None:
    return
  payload = json.dumps(action, default=str).encode("utf-8")
  await _producer.send_and_wait(TOPIC_ACTIONS, payload)


async def on_action_updated(action: dict) -> None:
  await publish_action(action)


async def ingest_ml_alerts():
  global _producer
  consumer = AIOKafkaConsumer(
    TOPIC_ML_ALERTS,
    bootstrap_servers=KAFKA_BOOTSTRAP,
    group_id="policy_engine",
    auto_offset_reset="latest",
  )
  await consumer.start()
  log.info("Consuming %s for policy evaluation", TOPIC_ML_ALERTS)

  rate_limit = int(engine.settings.get("max_actions_per_minute", 10))

  try:
    async for msg in consumer:
      try:
        alert = json.loads(msg.value.decode("utf-8"))
        matches = engine.evaluate(alert)
        if not matches:
          continue

        for rule in matches:
          if not store.check_rate_limit(rate_limit):
            log.warning("Rate limit exceeded — skipping action")
            break

          payload = engine.build_action(rule, alert)
          action = store.create(payload)

          if action.get("auto_execute"):
            executed = execute(action)
            store.update(action["action_id"], **executed)
            action = store.get(action["action_id"])
          else:
            log.info(
              "Pending approval: %s → %s on %s (alert %s)",
              action["rule_id"],
              action["action"],
              action["target"],
              action.get("alert_id", "?")[:8],
            )

          store.record_rate()
          await publish_action(action)

      except Exception as e:
        log.warning("Policy evaluation error: %s", e)
  finally:
    await consumer.stop()


async def ingest_commands():
  consumer = AIOKafkaConsumer(
    TOPIC_COMMANDS,
    bootstrap_servers=KAFKA_BOOTSTRAP,
    group_id="policy_engine_commands",
    auto_offset_reset="latest",
  )
  await consumer.start()
  log.info("Consuming %s for approve/reject", TOPIC_COMMANDS)

  try:
    async for msg in consumer:
      try:
        cmd = json.loads(msg.value.decode("utf-8"))
        action_id = cmd.get("action_id")
        command = cmd.get("command")
        if not action_id or not command:
          continue

        action = store.get(action_id)
        if not action:
          log.warning("Unknown action_id %s", action_id)
          continue

        if command == "approve" and action.get("status") == "pending":
          store.update(action_id, status="approved", approved_by=cmd.get("by", "analyst"))
          executed = execute(store.get(action_id))
          store.update(action_id, **executed)
          await publish_action(store.get(action_id))

        elif command == "reject" and action.get("status") == "pending":
          updated = store.update(
            action_id,
            status="rejected",
            rejected_by=cmd.get("by", "analyst"),
            rejection_reason=cmd.get("reason", ""),
          )
          await publish_action(updated)

        elif command == "rollback" and action.get("status") == "executed":
          from acds.policy_service.enforcer import rollback
          rolled = rollback(action)
          store.update(action_id, **rolled)
          await publish_action(store.get(action_id))

      except Exception as e:
        log.warning("Command processing error: %s", e)
  finally:
    await consumer.stop()


def start_api_server():
  init_api(store, engine, on_approve=on_action_updated)
  config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=API_PORT, log_level="warning")
  server = uvicorn.Server(config)
  thread = threading.Thread(target=server.run, daemon=True)
  thread.start()
  log.info("Policy API on port %d", API_PORT)


async def main():
  global _producer
  _producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
  await _producer.start()

  start_api_server()

  print("=" * 65)
  print("  ACDS RESPONSE & POLICY ENGINE")
  print(f"  Rules:     {len(engine.rules)} YAML rules loaded")
  print(f"  Consume:   {TOPIC_ML_ALERTS}, {TOPIC_COMMANDS}")
  print(f"  Publish:   {TOPIC_ACTIONS}")
  print(f"  API:       http://0.0.0.0:{API_PORT}/api/policy/summary")
  print(f"  Dry run:   {engine.settings.get('dry_run', True)} (set ENFORCE=true for real iptables)")
  print("=" * 65)

  try:
    await asyncio.gather(ingest_ml_alerts(), ingest_commands())
  finally:
    await _producer.stop()


def shutdown(sig, frame):
  log.info("Shutting down policy engine...")
  sys.exit(0)


if __name__ == "__main__":
  signal.signal(signal.SIGINT, shutdown)
  signal.signal(signal.SIGTERM, shutdown)
  asyncio.run(main())
