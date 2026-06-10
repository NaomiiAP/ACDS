"""
action_store.py — In-memory store for policy actions (pending / executed).
"""

import threading
import time
import uuid
from typing import Optional


class ActionStore:
  def __init__(self, max_size: int = 2000):
    self._actions: dict[str, dict] = {}
    self._lock = threading.Lock()
    self.max_size = max_size
    self._rate_window: list[float] = []

  def _trim(self) -> None:
    if len(self._actions) <= self.max_size:
      return
    oldest = sorted(self._actions.values(), key=lambda a: a.get("timestamp", 0))
    for a in oldest[: len(self._actions) - self.max_size]:
      self._actions.pop(a["action_id"], None)

  def check_rate_limit(self, limit: int) -> bool:
    now = time.time()
    with self._lock:
      self._rate_window = [t for t in self._rate_window if now - t < 60]
      return len(self._rate_window) < limit

  def record_rate(self) -> None:
    with self._lock:
      self._rate_window.append(time.time())

  def create(self, payload: dict) -> dict:
    action = {
      "action_id": str(uuid.uuid4()),
      "timestamp": time.time(),
      "status": "pending",
      "requested_by": "policy_engine",
      **payload,
    }
    with self._lock:
      self._actions[action["action_id"]] = action
      self._trim()
    return action

  def get(self, action_id: str) -> Optional[dict]:
    with self._lock:
      return self._actions.get(action_id)

  def update(self, action_id: str, **fields) -> Optional[dict]:
    with self._lock:
      action = self._actions.get(action_id)
      if not action:
        return None
      action.update(fields)
      return dict(action)

  def list_all(self, limit: int = 100) -> list[dict]:
    with self._lock:
      items = sorted(self._actions.values(), key=lambda a: a.get("timestamp", 0), reverse=True)
      return items[:limit]

  def list_pending(self) -> list[dict]:
    with self._lock:
      return [
        a for a in self._actions.values()
        if a.get("status") == "pending"
      ]
