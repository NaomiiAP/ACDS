"""
risk_scorer.py — Rule-based threat scoring for enriched flows

Produces a risk_score (0.0–1.0) and risk_level ("low"|"medium"|"high").
This is a v1 rule-based implementation, designed to be replaced by an
ML model (sklearn / ONNX) in a later sprint without changing the interface.
"""


def score(event: dict) -> dict:
    """
    Takes an enriched flow dict and returns the same dict
    with risk_score and risk_level added.
    """
    s = 0.0
    reasons = []

    entropy = event.get("entropy", 0)
    burst_rate = event.get("burst_rate", 0)
    iat = event.get("inter_arrival_time", 0)
    tls_fp = event.get("tls_fingerprint", "none")
    dst_port = event.get("dst_port", 0)
    protocol = str(event.get("protocol", "")).upper()
    avg_size = event.get("avg_packet_size", 0)
    freq = event.get("connection_frequency", 0)
    process = str(event.get("process_name") or "unknown").lower()

    # ── High Entropy (likely encrypted / obfuscated payload)
    if entropy > 3.5:
        s += 0.35
        reasons.append("high_entropy")
    elif entropy > 2.8:
        s += 0.15
        reasons.append("moderate_entropy")

    # ── Burst Traffic (scanning / flooding)
    if burst_rate > 15:
        s += 0.30
        reasons.append("high_burst")
    elif burst_rate > 8:
        s += 0.15
        reasons.append("moderate_burst")

    # ── C2 Beaconing indicator (long inter-arrival time on TCP)
    if iat > 5.0 and protocol == "TCP":
        s += 0.25
        reasons.append("c2_timing_pattern")
    elif iat > 2.0 and protocol == "TCP":
        s += 0.10
        reasons.append("slow_tcp_timing")

    # ── HTTPS port but no TLS handshake detected
    if dst_port == 443 and tls_fp == "none":
        s += 0.30
        reasons.append("https_no_tls_handshake")

    # ── Unusual TLS version (not TLS 1.2 or 1.3)
    if tls_fp not in ("none", "TLS_0303_HS_1", "TLS_0303_HS_2",
                       "TLS_0304_HS_1", "TLS_0304_HS_2"):
        s += 0.20
        reasons.append("unusual_tls_version")

    # ── Known risky ports
    risky_ports = {22, 23, 3389, 4444, 1337, 31337, 8080, 8443}
    if dst_port in risky_ports:
        s += 0.20
        reasons.append(f"risky_port_{dst_port}")

    # ── Very large packets (possible data exfiltration)
    if avg_size > 1400:
        s += 0.15
        reasons.append("large_avg_packet_size")

    # ── High connection frequency from same flow (DDoS / scan)
    if freq > 100:
        s += 0.20
        reasons.append("high_connection_frequency")

    # ── Known noisy/system processes get a small reduction
    safe_procs = {"curl", "wget", "ping", "nslookup", "dig", "ssh", "browser"}
    if process in safe_procs:
        s = max(0.0, s - 0.10)

    # ── Unknown process attribution is itself slightly suspicious
    if process == "unknown":
        s += 0.10
        reasons.append("unknown_process")

    risk_score = round(min(s, 1.0), 3)

    if risk_score >= 0.60:
        risk_level = "high"
    elif risk_score >= 0.30:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        **event,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_reasons": reasons,
    }
