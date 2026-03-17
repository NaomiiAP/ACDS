"""
flow_correlator.py — Joins DPI feature vectors with Telemetry metadata.

When a dpi.features event arrives:
1. Build canonical flow key from (src_ip, src_port, dst_ip, dst_port, protocol)
2. Look up in TTL store for a matching telemetry connect event
3. Merge both payloads into an enriched flow
4. Apply risk scoring
5. Return enriched event ready for Kafka publish
"""
import time
from state_store import registry
from risk_scorer import score


def correlate(dpi_event: dict) -> dict:
    """
    Returns an enriched + scored event dict.
    If no telemetry match found, process_name is set to "unknown".
    """
    src_ip   = dpi_event.get("src_ip", "")
    src_port = int(dpi_event.get("src_port", 0))
    dst_ip   = dpi_event.get("dst_ip", "")
    dst_port = int(dpi_event.get("dst_port", 0))
    protocol = dpi_event.get("protocol", "TCP")

    # Attempt correlation with telemetry registry
    telemetry_meta = registry.lookup(src_ip, src_port, dst_ip, dst_port, protocol)

    if telemetry_meta:
        # Check timing window (DPI timestamp vs telemetry timestamp = ±5s)
        dpi_ts = dpi_event.get("timestamp", time.time())
        tel_ts = telemetry_meta.get("timestamp", 0)
        if abs(dpi_ts - tel_ts) <= 5.0 or tel_ts == 0:
            process_name  = telemetry_meta.get("process_name", "unknown")
            pid           = telemetry_meta.get("pid", -1)
            container_id  = telemetry_meta.get("container_id", "")
            host_id       = telemetry_meta.get("host_id", "")
        else:
            # Stale telemetry match — ignore attribution
            process_name, pid, container_id, host_id = "unknown", -1, "", ""
    else:
        process_name, pid, container_id, host_id = "unknown", -1, "", ""

    enriched = {
        "schema_version":   "1.0",
        "host_id":          host_id,
        "pid":              pid,
        "process_name":     process_name,
        "container_id":     container_id,
        "src_ip":           src_ip,
        "src_port":         src_port,
        "dst_ip":           dst_ip,
        "dst_port":         dst_port,
        "protocol":         protocol,
        "timestamp":        dpi_event.get("timestamp", time.time()),

        # DPI features
        "connection_frequency":  dpi_event.get("connection_frequency", 0),
        "avg_packet_size":       dpi_event.get("avg_packet_size", 0),
        "entropy":               dpi_event.get("entropy", 0),
        "burst_rate":            dpi_event.get("burst_rate", 0),
        "inter_arrival_time":    dpi_event.get("inter_arrival_time", 0),
        "tls_fingerprint":       dpi_event.get("tls_fingerprint", "none"),
        "correlated":            telemetry_meta is not None,
    }

    # Apply risk scoring
    return score(enriched)
