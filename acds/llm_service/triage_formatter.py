"""
triage_formatter.py — Parse raw LLM output into structured triage JSON.
"""

import re
import logging

log = logging.getLogger("llm_triage.formatter")

VALID_ATTACK_STAGES = {
    "reconnaissance", "initial_access", "execution", "persistence",
    "lateral_movement", "privilege_escalation", "exfiltration",
    "command_and_control", "impact", "unknown",
}

VALID_CONFIDENCE = {"low", "medium", "high"}

VALID_SEVERITY = {"informational", "low", "medium", "high", "critical"}

# Defaults when parsing fails
DEFAULTS = {
    "explanation": "Analysis could not be completed",
    "attack_stage": "unknown",
    "confidence": "low",
    "severity": "medium",
    "mitigation_steps": ["Review alert details manually"],
}


def _extract_field(text: str, label: str) -> str | None:
    """Extract the value after 'LABEL:' up to the next known label or end."""
    pattern = rf"{label}\s*:\s*(.+?)(?=\n(?:EXPLANATION|ATTACK_STAGE|CONFIDENCE|SEVERITY|MITIGATION)\s*:|$)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _extract_mitigation(text: str) -> list[str]:
    """Extract bullet-pointed mitigation steps after 'MITIGATION:'."""
    pattern = r"MITIGATION\s*:\s*\n?((?:\s*-\s*.+\n?)+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return []
    block = match.group(1)
    steps = re.findall(r"-\s*(.+)", block)
    return [s.strip() for s in steps if s.strip()]


def parse_llm_output(raw_text: str) -> dict:
    """Parse structured fields from the LLM's raw text response.

    Returns a dict with keys: explanation, attack_stage, confidence,
    severity, mitigation_steps.  Falls back to defaults for any field
    that cannot be parsed or validated.
    """
    result = {}

    # --- explanation ---
    explanation = _extract_field(raw_text, "EXPLANATION")
    result["explanation"] = explanation if explanation else DEFAULTS["explanation"]

    # --- attack_stage ---
    raw_stage = _extract_field(raw_text, "ATTACK_STAGE")
    if raw_stage:
        normalised = raw_stage.strip().lower().replace(" ", "_")
        result["attack_stage"] = normalised if normalised in VALID_ATTACK_STAGES else DEFAULTS["attack_stage"]
    else:
        result["attack_stage"] = DEFAULTS["attack_stage"]

    # --- confidence ---
    raw_conf = _extract_field(raw_text, "CONFIDENCE")
    if raw_conf:
        normalised = raw_conf.strip().lower()
        result["confidence"] = normalised if normalised in VALID_CONFIDENCE else DEFAULTS["confidence"]
    else:
        result["confidence"] = DEFAULTS["confidence"]

    # --- severity ---
    raw_sev = _extract_field(raw_text, "SEVERITY")
    if raw_sev:
        normalised = raw_sev.strip().lower()
        result["severity"] = normalised if normalised in VALID_SEVERITY else DEFAULTS["severity"]
    else:
        result["severity"] = DEFAULTS["severity"]

    # --- mitigation_steps ---
    steps = _extract_mitigation(raw_text)
    result["mitigation_steps"] = steps if steps else DEFAULTS["mitigation_steps"]

    return result
