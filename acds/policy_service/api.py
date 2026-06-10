"""
api.py — REST API for the ACDS Policy Engine (port 8200).
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from acds.policy_service.action_store import ActionStore
from acds.policy_service.enforcer import execute, get_enforcement_state, rollback
from acds.policy_service.rule_engine import RuleEngine

log = logging.getLogger("policy_service.api")

_store: ActionStore | None = None
_engine: RuleEngine | None = None
_on_approve = None  # callback set by policy_main


def init_api(store: ActionStore, engine: RuleEngine, on_approve=None) -> None:
  global _store, _engine, _on_approve
  _store = store
  _engine = engine
  _on_approve = on_approve


@asynccontextmanager
async def lifespan(app: FastAPI):
  if _store is None or _engine is None:
    init_api(ActionStore(), RuleEngine())
  yield


app = FastAPI(title="ACDS Policy Engine API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_methods=["*"],
  allow_headers=["*"],
)


@app.get("/api/policy/summary")
async def summary():
  store = _store
  engine = _engine
  pending = store.list_pending() if store else []
  all_actions = store.list_all(500) if store else []
  executed = sum(1 for a in all_actions if a.get("status") == "executed")
  return {
    "rules_loaded": len(engine.rules) if engine else 0,
    "pending_approvals": len(pending),
    "total_actions": len(all_actions),
    "executed": executed,
    **get_enforcement_state(),
  }


@app.get("/api/policy/rules")
async def list_rules():
  if not _engine:
    raise HTTPException(503, "Policy engine not ready")
  return {"rules": _engine.list_rules(), "settings": _engine.settings}


@app.post("/api/policy/rules/reload")
async def reload_rules():
  if not _engine:
    raise HTTPException(503, "Policy engine not ready")
  _engine.reload()
  return {"ok": True, "rules": len(_engine.rules)}


@app.get("/api/policy/actions")
async def list_actions(limit: int = 100, status: Optional[str] = None):
  if not _store:
    raise HTTPException(503, "Action store not ready")
  actions = _store.list_all(limit)
  if status:
    actions = [a for a in actions if a.get("status") == status]
  return {"actions": actions, "count": len(actions)}


@app.get("/api/policy/actions/{action_id}")
async def get_action(action_id: str):
  action = _store.get(action_id) if _store else None
  if not action:
    raise HTTPException(404, "Action not found")
  return action


@app.post("/api/policy/actions/{action_id}/approve")
async def approve_action(action_id: str, approved_by: str = "analyst"):
  action = _store.get(action_id) if _store else None
  if not action:
    raise HTTPException(404, "Action not found")
  if action.get("status") != "pending":
    raise HTTPException(400, f"Action status is {action.get('status')}, not pending")

  action = _store.update(
    action_id,
    status="approved",
    approved_by=approved_by,
    approved_at=time.time(),
  )
  executed = execute(action)
  _store.update(action_id, **executed)
  if _on_approve:
    await _on_approve(executed)
  return executed


@app.post("/api/policy/actions/{action_id}/reject")
async def reject_action(action_id: str, rejected_by: str = "analyst", reason: str = ""):
  action = _store.get(action_id) if _store else None
  if not action:
    raise HTTPException(404, "Action not found")
  if action.get("status") != "pending":
    raise HTTPException(400, f"Action status is {action.get('status')}, not pending")

  updated = _store.update(
    action_id,
    status="rejected",
    rejected_by=rejected_by,
    rejection_reason=reason,
    rejected_at=time.time(),
  )
  if _on_approve:
    await _on_approve(updated)
  return updated


@app.post("/api/policy/actions/{action_id}/rollback")
async def rollback_action(action_id: str):
  action = _store.get(action_id) if _store else None
  if not action:
    raise HTTPException(404, "Action not found")
  if action.get("status") != "executed":
    raise HTTPException(400, "Only executed actions can be rolled back")
  rolled = rollback(action)
  _store.update(action_id, **rolled)
  return rolled


@app.post("/api/policy/evaluate")
async def evaluate_alert(alert: dict):
  """Manually evaluate an alert against YAML rules (debug / UI)."""
  if not _engine or not _store:
    raise HTTPException(503, "Policy engine not ready")
  matches = _engine.evaluate(alert)
  return {"matches": matches, "count": len(matches)}
