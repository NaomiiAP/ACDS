"""
enforcer.py — Execute remediation actions (block IP, isolate process, throttle).

Default: DRY_RUN logs to audit file. Set ENFORCE=true for real iptables (requires root).
"""

import json
import logging
import os
import subprocess
import time
from pathlib import Path

log = logging.getLogger("policy_service.enforcer")

AUDIT_PATH = Path(os.getenv("ACDS_POLICY_AUDIT", Path(__file__).parent / "audit.log"))
_isolated_processes: set[str] = set()
_blocked_ips: set[str] = set()


def _audit(entry: dict) -> None:
  entry["audit_ts"] = time.time()
  line = json.dumps(entry, default=str)
  AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
  with open(AUDIT_PATH, "a", encoding="utf-8") as f:
    f.write(line + "\n")
  log.info("AUDIT: %s → %s (%s)", entry.get("action"), entry.get("target"), entry.get("status"))


def is_dry_run(action: dict) -> bool:
  if os.getenv("ENFORCE", "").lower() in ("1", "true", "yes"):
    return False
  return bool(action.get("dry_run", True))


def execute(action: dict) -> dict:
  """Run remediation; returns updated action with status and result message."""
  action_type = action.get("action", "alert_only")
  target = action.get("target", "")
  dry = is_dry_run(action)

  try:
    if action_type == "block_ip":
      result = _block_ip(target, dry)
    elif action_type == "isolate_process":
      result = _isolate_process(target, action, dry)
    elif action_type == "throttle":
      result = _throttle(target, dry)
    elif action_type == "alert_only":
      result = {"message": f"Advisory logged for {target}", "simulated": True}
    else:
      result = {"message": f"Unknown action type: {action_type}", "simulated": True}

    action["status"] = "executed"
    action["executed_at"] = time.time()
    action["result"] = result
    action["dry_run"] = dry
    _audit({**action, "status": "executed"})
    return action

  except Exception as e:
    log.error("Enforcement failed: %s", e)
    action["status"] = "failed"
    action["result"] = {"error": str(e)}
    _audit({**action, "status": "failed"})
    return action


def rollback(action: dict) -> dict:
  """Best-effort undo for block_ip / isolate markers."""
  action_type = action.get("action")
  target = action.get("target", "")
  dry = is_dry_run(action)

  if action_type == "block_ip" and target in _blocked_ips:
    _blocked_ips.discard(target)
    if not dry:
      subprocess.run(
        ["iptables", "-D", "INPUT", "-s", target, "-j", "DROP"],
        check=False,
        capture_output=True,
      )
  elif action_type == "isolate_process" and target in _isolated_processes:
    _isolated_processes.discard(target)

  action["status"] = "rolled_back"
  action["rolled_back_at"] = time.time()
  _audit({**action, "status": "rolled_back"})
  return action


def _block_ip(ip: str, dry: bool) -> dict:
  if not ip:
    raise ValueError("block_ip requires a target IP")
  _blocked_ips.add(ip)
  if dry:
    return {"message": f"[DRY RUN] Would block IP {ip} via iptables INPUT DROP", "simulated": True}
  subprocess.run(
    ["iptables", "-A", "INPUT", "-s", ip, "-j", "DROP"],
    check=True,
    capture_output=True,
    text=True,
  )
  return {"message": f"Blocked IP {ip} (iptables INPUT DROP)", "simulated": False}


def _isolate_process(target: str, action: dict, dry: bool) -> dict:
  if not target:
    raise ValueError("isolate_process requires a process target")
  _isolated_processes.add(target)
  summary = action.get("alert_summary", {})
  pid = summary.get("pid") or _parse_pid(target)

  if dry:
    return {
      "message": f"[DRY RUN] Would isolate process {target} (network quarantine / SIGSTOP)",
      "simulated": True,
      "isolated": True,
    }

  if pid:
    try:
      os.kill(int(pid), 19)  # SIGSTOP — demo isolation
      return {"message": f"Process {target} paused (SIGSTOP)", "simulated": False, "pid": pid}
    except (ProcessLookupError, PermissionError) as e:
      return {"message": f"Marked isolated; could not SIGSTOP pid {pid}: {e}", "simulated": False}

  return {"message": f"Process {target} marked isolated (no PID)", "simulated": False}


def _throttle(target: str, dry: bool) -> dict:
  if dry:
    return {"message": f"[DRY RUN] Would throttle traffic from {target} (tc rate limit)", "simulated": True}
  return {"message": f"Throttle applied to {target} (tc not configured — logged only)", "simulated": True}


def _parse_pid(target: str) -> int | None:
  if ":" in target:
    try:
      return int(target.rsplit(":", 1)[-1])
    except ValueError:
      return None
  return None


def get_enforcement_state() -> dict:
  return {
    "dry_run": os.getenv("ENFORCE", "").lower() not in ("1", "true", "yes"),
    "blocked_ips": sorted(_blocked_ips),
    "isolated_processes": sorted(_isolated_processes),
    "audit_path": str(AUDIT_PATH),
  }
