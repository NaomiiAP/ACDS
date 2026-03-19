"""
prompt_templates.py — Structured prompt builder for LLM triage analysis.
"""

TRIAGE_TEMPLATE = """\
You are a cybersecurity analyst at a Security Operations Center. Analyze the following network security alert detected by our ML-based threat detection system.

## Alert Summary
- Ensemble Detection Score: {ensemble_score}/1.0
- Supervised Model Prediction: {predicted_label} (confidence: {supervised_score})
- Anomaly Detection Score: {unsupervised_score}/1.0
- Risk Level: {risk_level}

## Network Flow
- Source: {src_ip}:{src_port} → Destination: {dst_ip}:{dst_port}
- Protocol: {protocol}
- Process: {process_name} (PID: {pid})
- Container: {container_id}
- Host: {host_id}

## DPI Features
- Connection Frequency: {connection_frequency} packets
- Average Packet Size: {avg_packet_size} bytes
- Payload Entropy: {entropy}
- Burst Rate: {burst_rate}
- Inter-Arrival Time: {inter_arrival_time}s
- TLS Fingerprint: {tls_fingerprint}

## Rule-Based Detection Reasons
{risk_reasons}

Provide your analysis in EXACTLY this format:

EXPLANATION: [1-3 sentences explaining what is happening and why it's suspicious]
ATTACK_STAGE: [one of: reconnaissance, initial_access, execution, persistence, lateral_movement, privilege_escalation, exfiltration, command_and_control, impact, unknown]
CONFIDENCE: [low, medium, or high]
SEVERITY: [informational, low, medium, high, or critical]
MITIGATION:
- [step 1]
- [step 2]
- [step 3]"""


def build_prompt(alert: dict) -> str:
    """Fill the triage prompt template with values from an alert dict.

    Missing keys are replaced with sensible defaults so the prompt is
    always well-formed even if the upstream alert is incomplete.
    """
    risk_reasons_raw = alert.get("risk_reasons", [])
    if isinstance(risk_reasons_raw, list):
        risk_reasons = "\n".join(f"- {r}" for r in risk_reasons_raw) if risk_reasons_raw else "- None reported"
    else:
        risk_reasons = str(risk_reasons_raw) if risk_reasons_raw else "- None reported"

    return TRIAGE_TEMPLATE.format(
        ensemble_score=alert.get("ensemble_score", "N/A"),
        predicted_label=alert.get("predicted_label", "unknown"),
        supervised_score=alert.get("supervised_score", "N/A"),
        unsupervised_score=alert.get("unsupervised_score", "N/A"),
        risk_level=alert.get("risk_level", "unknown"),
        src_ip=alert.get("src_ip", "0.0.0.0"),
        src_port=alert.get("src_port", 0),
        dst_ip=alert.get("dst_ip", "0.0.0.0"),
        dst_port=alert.get("dst_port", 0),
        protocol=alert.get("protocol", "TCP"),
        process_name=alert.get("process_name", "unknown"),
        pid=alert.get("pid", "N/A"),
        container_id=alert.get("container_id", "N/A"),
        host_id=alert.get("host_id", "N/A"),
        connection_frequency=alert.get("connection_frequency", "N/A"),
        avg_packet_size=alert.get("avg_packet_size", "N/A"),
        entropy=alert.get("entropy", "N/A"),
        burst_rate=alert.get("burst_rate", "N/A"),
        inter_arrival_time=alert.get("inter_arrival_time", "N/A"),
        tls_fingerprint=alert.get("tls_fingerprint", "N/A"),
        risk_reasons=risk_reasons,
    )
