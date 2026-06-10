"""
rule_engine.py — YAML-based policy rule evaluation for ML alerts.
"""

import logging
import os
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger("policy_service.rules")

DEFAULT_POLICIES = Path(__file__).parent / "policies.yaml"


class RuleEngine:
  def __init__(self, policies_path: str | None = None):
    self.policies_path = Path(policies_path or os.getenv("ACDS_POLICIES_PATH", DEFAULT_POLICIES))
    self._config: dict = {}
    self.reload()

  def reload(self) -> None:
    with open(self.policies_path, encoding="utf-8") as f:
      self._config = yaml.safe_load(f) or {}
    rules = self._config.get("rules", [])
    log.info("Loaded %d policy rules from %s", len(rules), self.policies_path)

  @property
  def settings(self) -> dict:
    return self._config.get("settings", {})

  @property
  def rules(self) -> list[dict]:
    return [r for r in self._config.get("rules", []) if r.get("enabled", True)]

  def list_rules(self) -> list[dict]:
    return self._config.get("rules", [])

  def evaluate(self, alert: dict) -> list[dict]:
    """Return list of matching rules (with resolved targets)."""
    matches = []
    score = float(alert.get("ensemble_score", 0))
    label = str(alert.get("predicted_label", ""))
    risk = str(alert.get("risk_level", "")).lower()
    dst_port = int(alert.get("dst_port", 0))

    for rule in self.rules:
      m = rule.get("match", {})
      min_score = float(m.get("min_ensemble_score", 0))
      max_score = m.get("max_ensemble_score")
      if score < min_score:
        continue
      if max_score is not None and score > float(max_score):
        continue

      allowed_labels = m.get("labels")
      if allowed_labels and label not in allowed_labels:
        continue

      allowed_risk = m.get("risk_levels")
      if allowed_risk and risk not in [r.lower() for r in allowed_risk]:
        continue

      allowed_ports = m.get("dst_ports")
      if allowed_ports and dst_port not in allowed_ports:
        continue

      target = self._resolve_target(rule.get("target", "process"), alert)
      if not target:
        continue

      matches.append({**rule, "resolved_target": target})

    return matches

  @staticmethod
  def _resolve_target(target_kind: str, alert: dict) -> str | None:
    kind = (target_kind or "process").lower()
    if kind == "dst_ip":
      return alert.get("dst_ip") or None
    if kind == "src_ip":
      return alert.get("src_ip") or None
    if kind == "process":
      name = alert.get("process_name")
      pid = alert.get("pid")
      if name and pid:
        return f"{name}:{pid}"
      return name or None
    if kind == "container":
      return alert.get("container_id") or None
    if kind == "host":
      return alert.get("host_id") or None
    return None

  def build_action(self, rule: dict, alert: dict) -> dict:
    settings = self.settings
    require_approval = rule.get(
      "require_approval",
      settings.get("default_require_approval", True),
    )
    auto_execute = bool(rule.get("auto_execute", False))
    if require_approval:
      auto_execute = False

    action_type = rule.get("action", "alert_only")
    target = rule.get("resolved_target", "")

    return {
      "rule_id": rule.get("id", "unknown"),
      "rule_description": rule.get("description", ""),
      "action": action_type,
      "target_type": rule.get("target", "process"),
      "target": target,
      "alert_id": alert.get("alert_id", ""),
      "human_override_required": require_approval,
      "auto_execute": auto_execute,
      "dry_run": settings.get("dry_run", True),
      "alert_summary": {
        "ensemble_score": alert.get("ensemble_score"),
        "predicted_label": alert.get("predicted_label"),
        "risk_level": alert.get("risk_level"),
        "process_name": alert.get("process_name"),
        "pid": alert.get("pid"),
        "dst_ip": alert.get("dst_ip"),
        "dst_port": alert.get("dst_port"),
      },
    }
