"""
graph_schema.py — Cypher query builders for the ACDS Attack Graph.

Node types:
    (:Host), (:Container), (:Process), (:IP), (:Service)

Edge types:
    CONNECTED_TO, SUSPICIOUS_CONNECTION, HOSTS, RUNS

Every builder returns a (cypher_string, params_dict) tuple so that the
caller can execute them via neo4j_client.execute_write.
"""

import time
from typing import Any

# ── Node MERGE queries ──────────────────────────────────────────────


def merge_host(host_id: str, risk_score: float = 0.0, timestamp: float | None = None) -> tuple[str, dict]:
    ts = timestamp or time.time()
    query = (
        "MERGE (h:Host {id: $host_id}) "
        "ON CREATE SET h.hostname = $host_id, h.risk_score = $risk_score, "
        "  h.last_seen = $ts, h.event_count = 1 "
        "ON MATCH SET h.risk_score = CASE WHEN $risk_score > h.risk_score "
        "  THEN $risk_score ELSE h.risk_score END, "
        "  h.last_seen = $ts, h.event_count = h.event_count + 1"
    )
    return query, {"host_id": host_id, "risk_score": risk_score, "ts": ts}


def merge_container(container_id: str, host_id: str, timestamp: float | None = None) -> tuple[str, dict]:
    ts = timestamp or time.time()
    query = (
        "MERGE (c:Container {id: $container_id}) "
        "ON CREATE SET c.host_id = $host_id, c.risk_score = 0.0, c.last_seen = $ts "
        "ON MATCH SET c.last_seen = $ts"
    )
    return query, {"container_id": container_id, "host_id": host_id, "ts": ts}


def merge_process(
    pid: int,
    name: str,
    container_id: str,
    host_id: str,
    risk_score: float = 0.0,
    timestamp: float | None = None,
) -> tuple[str, dict]:
    ts = timestamp or time.time()
    query = (
        "MERGE (p:Process {pid: $pid, host_id: $host_id}) "
        "ON CREATE SET p.name = $name, p.container_id = $container_id, "
        "  p.risk_score = $risk_score, p.last_seen = $ts "
        "ON MATCH SET p.name = $name, p.risk_score = CASE WHEN $risk_score > p.risk_score "
        "  THEN $risk_score ELSE p.risk_score END, p.last_seen = $ts"
    )
    return query, {
        "pid": pid,
        "name": name,
        "container_id": container_id,
        "host_id": host_id,
        "risk_score": risk_score,
        "ts": ts,
    }


def merge_ip(address: str, is_internal: bool = False, risk_score: float = 0.0, timestamp: float | None = None) -> tuple[str, dict]:
    ts = timestamp or time.time()
    query = (
        "MERGE (ip:IP {address: $address}) "
        "ON CREATE SET ip.is_internal = $is_internal, ip.risk_score = $risk_score, ip.last_seen = $ts "
        "ON MATCH SET ip.risk_score = CASE WHEN $risk_score > ip.risk_score "
        "  THEN $risk_score ELSE ip.risk_score END, ip.last_seen = $ts"
    )
    return query, {"address": address, "is_internal": is_internal, "risk_score": risk_score, "ts": ts}


# ── Edge CREATE / MERGE queries ─────────────────────────────────────


def create_connection_edge(
    process_pid: int,
    process_host_id: str,
    ip_address: str,
    timestamp: float | None = None,
    risk_score: float = 0.0,
    alert_id: str = "",
    protocol: str = "TCP",
    dst_port: int = 0,
) -> tuple[str, dict]:
    ts = timestamp or time.time()
    query = (
        "MATCH (p:Process {pid: $pid, host_id: $host_id}), (ip:IP {address: $address}) "
        "CREATE (p)-[:CONNECTED_TO {"
        "  timestamp: $ts, risk_score: $risk_score, alert_id: $alert_id, "
        "  protocol: $protocol, dst_port: $dst_port"
        "}]->(ip)"
    )
    return query, {
        "pid": process_pid,
        "host_id": process_host_id,
        "address": ip_address,
        "ts": ts,
        "risk_score": risk_score,
        "alert_id": alert_id,
        "protocol": protocol,
        "dst_port": dst_port,
    }


def create_suspicious_edge(
    process_pid: int,
    process_host_id: str,
    ip_address: str,
    ensemble_score: float,
    predicted_label: str,
    timestamp: float | None = None,
    alert_id: str = "",
) -> tuple[str, dict]:
    ts = timestamp or time.time()
    query = (
        "MATCH (p:Process {pid: $pid, host_id: $host_id}), (ip:IP {address: $address}) "
        "CREATE (p)-[:SUSPICIOUS_CONNECTION {"
        "  ensemble_score: $ensemble_score, predicted_label: $predicted_label, "
        "  timestamp: $ts, alert_id: $alert_id"
        "}]->(ip)"
    )
    return query, {
        "pid": process_pid,
        "host_id": process_host_id,
        "address": ip_address,
        "ensemble_score": ensemble_score,
        "predicted_label": predicted_label,
        "ts": ts,
        "alert_id": alert_id,
    }


def create_host_container_edge(host_id: str, container_id: str) -> tuple[str, dict]:
    query = (
        "MATCH (h:Host {id: $host_id}), (c:Container {id: $container_id}) "
        "MERGE (h)-[:HOSTS]->(c)"
    )
    return query, {"host_id": host_id, "container_id": container_id}


def create_container_process_edge(container_id: str, pid: int, host_id: str) -> tuple[str, dict]:
    query = (
        "MATCH (c:Container {id: $container_id}), (p:Process {pid: $pid, host_id: $host_id}) "
        "MERGE (c)-[:RUNS]->(p)"
    )
    return query, {"container_id": container_id, "pid": pid, "host_id": host_id}


def create_host_process_edge(host_id: str, pid: int) -> tuple[str, dict]:
    """Link host to process when no container is present (demo alerts)."""
    query = (
        "MATCH (h:Host {id: $host_id}), (p:Process {pid: $pid, host_id: $host_id}) "
        "MERGE (h)-[:RUNS]->(p)"
    )
    return query, {"host_id": host_id, "pid": pid}


# ── Composite builder ───────────────────────────────────────────────


def _is_internal(ip: str) -> bool:
    """Heuristic: RFC-1918 and loopback are internal."""
    return (
        ip.startswith("10.")
        or ip.startswith("172.16.")
        or ip.startswith("172.17.")
        or ip.startswith("192.168.")
        or ip.startswith("127.")
    )


def build_graph_from_alert(alert: dict) -> list[tuple[str, dict]]:
    """
    Given an ml.alerts event, return a list of (cypher, params) pairs that
    together build the subgraph for this alert.

    Expected alert keys (all optional – missing ones are gracefully skipped):
        host_id, container_id, pid, process_name, src_ip, dst_ip, dst_port,
        protocol, ensemble_score, predicted_label, alert_id, timestamp
    """
    ops: list[tuple[str, dict]] = []
    ts = alert.get("timestamp", time.time())
    ensemble_score = float(alert.get("ensemble_score", 0.0))
    host_id = alert.get("host_id", "unknown")
    container_id = alert.get("container_id", "")
    pid = alert.get("pid")
    process_name = alert.get("process_name", "unknown")
    dst_ip = alert.get("dst_ip", "")
    dst_port = int(alert.get("dst_port", 0))
    protocol = str(alert.get("protocol", "TCP")).upper()
    alert_id = alert.get("alert_id", "")
    predicted_label = alert.get("predicted_label", "unknown")

    # 1. MERGE Host
    ops.append(merge_host(host_id, risk_score=ensemble_score, timestamp=ts))

    # 2. MERGE Container (if present)
    if container_id:
        ops.append(merge_container(container_id, host_id, timestamp=ts))
        ops.append(create_host_container_edge(host_id, container_id))

    # 3. MERGE Process (if pid present)
    if pid is not None:
        pid = int(pid)
        ops.append(merge_process(pid, process_name, container_id, host_id, ensemble_score, ts))
        if container_id:
            ops.append(create_container_process_edge(container_id, pid, host_id))
        else:
            ops.append(create_host_process_edge(host_id, pid))

    # 4. MERGE destination IP
    if dst_ip:
        ops.append(merge_ip(dst_ip, _is_internal(dst_ip), ensemble_score, ts))

    # 5. Edge: Process -> IP
    if pid is not None and dst_ip:
        if ensemble_score >= 0.5:
            ops.append(create_suspicious_edge(
                pid, host_id, dst_ip, ensemble_score, predicted_label, ts, alert_id,
            ))
        else:
            ops.append(create_connection_edge(
                pid, host_id, dst_ip, ts, ensemble_score, alert_id, protocol, dst_port,
            ))

    return ops
