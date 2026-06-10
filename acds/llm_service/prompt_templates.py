"""
prompt_templates.py — Structured prompt builder for LLM triage analysis.
"""

import json

def build_prompt(alert: dict) -> str:
    """Create a structured prompt for the LLM based on the alert data."""
    
    # Extract relevant fields for the prompt
    alert_context = {
        "ensemble_score": alert.get("ensemble_score"),
        "predicted_label": alert.get("predicted_label"),
        "risk_level": alert.get("risk_level"),
        "src_ip": alert.get("src_ip"),
        "dst_ip": alert.get("dst_ip"),
        "dst_port": alert.get("dst_port"),
        "protocol": alert.get("protocol"),
        "process_name": alert.get("process_name"),
        "pid": alert.get("pid"),
        "risk_reasons": alert.get("risk_reasons"),
        "features": {k: v for k, v in alert.get("features", {}).items() if not k.startswith("window_")},
    }

    prompt = f"""
Analyze the following security alert and provide a triage report.
You MUST follow this format exactly:

EXPLANATION: [A brief summary of the threat]
ATTACK_STAGE: [reconnaissance, initial_access, execution, persistence, lateral_movement, privilege_escalation, exfiltration, command_and_control, or impact]
CONFIDENCE: [low, medium, or high]
SEVERITY: [informational, low, medium, high, or critical]
MITIGATION:
- [step 1]
- [step 2]

ALERT DATA:
{json.dumps(alert_context, indent=2)}
"""
    return prompt.strip()
