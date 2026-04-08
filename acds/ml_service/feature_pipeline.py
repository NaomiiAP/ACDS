"""
feature_pipeline.py — Sliding time-window feature aggregation for ML detection.

Maintains per-flow sliding windows (10s, 30s, 60s) keyed by (src_ip, dst_ip, process_name).
Computes aggregate features used by the ML ensemble for real-time threat scoring.
"""

import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("ml_service.feature_pipeline")

# ---------------------------------------------------------------------------
# Flow record stored in window buffers
# ---------------------------------------------------------------------------

@dataclass
class FlowRecord:
    timestamp: float
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str
    process_name: str
    container_id: str
    host_id: str
    packet_size: float = 0.0
    entropy: float = 0.0
    burst_rate: float = 0.0
    inter_arrival_time: float = 0.0
    tls_fingerprint_encoded: float = 0.0
    risk_score: float = 0.0


# ---------------------------------------------------------------------------
# Feature pipeline
# ---------------------------------------------------------------------------

WINDOW_SIZES = (10, 30, 60)  # seconds


class FeaturePipeline:
    """Sliding-window feature aggregator keyed by (src_ip, dst_ip, process_name)."""

    def __init__(self, max_buffer_age: float = 120.0):
        # key -> list[FlowRecord], ordered by timestamp
        self._buffers: Dict[Tuple[str, str, str], List[FlowRecord]] = defaultdict(list)
        self._max_buffer_age = max_buffer_age
        # Track per-process connection counts (for lateral movement detection)
        self._process_connections: Dict[str, List[float]] = defaultdict(list)
        # Track per-container unique destination IPs
        self._container_dst_ips: Dict[str, Dict[str, float]] = defaultdict(dict)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_flow(self, flow: Dict[str, Any]) -> None:
        """Ingest an enriched flow event into the window buffers."""
        record = self._parse_flow(flow)
        key = (record.src_ip, record.dst_ip, record.process_name)
        self._buffers[key].append(record)

        # Track process connection count
        self._process_connections[record.process_name].append(record.timestamp)

        # Track container unique dst IPs
        if record.container_id:
            self._container_dst_ips[record.container_id][record.dst_ip] = record.timestamp

    def compute_features(self, flow: Dict[str, Any]) -> Dict[str, float]:
        """Compute the full 14-feature vector for a given flow event."""
        record = self._parse_flow(flow)
        key = (record.src_ip, record.dst_ip, record.process_name)
        now = record.timestamp

        # Purge expired entries from this key's buffer
        self._purge_buffer(key, now)

        buf = self._buffers.get(key, [])

        # --- Per-window aggregates ---
        window_counts = {}
        window_entropies = {}
        window_bursts = {}
        window_dst_ports: Dict[int, set] = {}

        for ws in WINDOW_SIZES:
            cutoff = now - ws
            in_window = [r for r in buf if r.timestamp >= cutoff]
            window_counts[ws] = len(in_window)

            if in_window:
                window_entropies[ws] = sum(r.entropy for r in in_window) / len(in_window)
                window_bursts[ws] = max(r.burst_rate for r in in_window)
                window_dst_ports[ws] = {r.dst_port for r in in_window}
            else:
                window_entropies[ws] = 0.0
                window_bursts[ws] = 0.0
                window_dst_ports[ws] = set()

        # --- Process connection count (60s window, lateral movement indicator) ---
        proc_name = record.process_name
        self._purge_process_connections(proc_name, now)
        process_connection_count = len(self._process_connections.get(proc_name, []))

        # --- Container unique dst IPs (60s window) ---
        container_id = record.container_id
        container_unique_dst_ips = 0
        if container_id:
            self._purge_container_dst_ips(container_id, now)
            container_unique_dst_ips = len(self._container_dst_ips.get(container_id, {}))

        features = {
            "connection_frequency": float(window_counts[10]),
            "avg_packet_size": record.packet_size,
            "entropy": record.entropy,
            "burst_rate": record.burst_rate,
            "inter_arrival_time": record.inter_arrival_time,
            "tls_fingerprint_encoded": record.tls_fingerprint_encoded,
            "window_10s_count": float(window_counts[10]),
            "window_30s_count": float(window_counts[30]),
            "window_60s_count": float(window_counts[60]),
            "window_avg_entropy": window_entropies[30],
            "window_max_burst": window_bursts[30],
            "window_unique_dst_ports": float(len(window_dst_ports[30])),
            "process_connection_count": float(process_connection_count),
            "container_unique_dst_ips": float(container_unique_dst_ips),
        }
        return features

    def cleanup(self, max_age: Optional[float] = None) -> int:
        """Remove stale buffers. Returns number of keys removed."""
        now = time.time()
        age = max_age or self._max_buffer_age
        stale_keys = []
        for key, buf in self._buffers.items():
            if not buf or (now - buf[-1].timestamp) > age:
                stale_keys.append(key)
        for key in stale_keys:
            del self._buffers[key]
        return len(stale_keys)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_flow(flow: Dict[str, Any]) -> FlowRecord:
        """Convert a raw enriched-flow dict into a FlowRecord."""
        return FlowRecord(
            timestamp=float(flow.get("timestamp", time.time())),
            src_ip=str(flow.get("src_ip", "")),
            dst_ip=str(flow.get("dst_ip", "")),
            src_port=int(flow.get("src_port", 0)),
            dst_port=int(flow.get("dst_port", 0)),
            protocol=str(flow.get("protocol", "TCP")).upper(),
            process_name=str(flow.get("process_name", "unknown")),
            container_id=str(flow.get("container_id", "")),
            host_id=str(flow.get("host_id", "")),
            packet_size=float(flow.get("avg_packet_size", flow.get("packet_size", 0.0))),
            entropy=float(flow.get("entropy", 0.0)),
            burst_rate=float(flow.get("burst_rate", 0.0)),
            inter_arrival_time=float(flow.get("inter_arrival_time", 0.0)),
            tls_fingerprint_encoded=float(flow.get("tls_fingerprint_encoded", 0.0)),
            risk_score=float(flow.get("risk_score", 0.0)),
        )

    def _purge_buffer(self, key: Tuple[str, str, str], now: float) -> None:
        cutoff = now - self._max_buffer_age
        buf = self._buffers.get(key)
        if buf:
            # Binary-style trim: drop everything older than cutoff
            idx = 0
            for i, r in enumerate(buf):
                if r.timestamp >= cutoff:
                    idx = i
                    break
            else:
                idx = len(buf)
            if idx > 0:
                self._buffers[key] = buf[idx:]

    def _purge_process_connections(self, proc_name: str, now: float) -> None:
        cutoff = now - 60.0
        timestamps = self._process_connections.get(proc_name, [])
        self._process_connections[proc_name] = [t for t in timestamps if t >= cutoff]

    def _purge_container_dst_ips(self, container_id: str, now: float) -> None:
        cutoff = now - 60.0
        dst_map = self._container_dst_ips.get(container_id, {})
        self._container_dst_ips[container_id] = {
            ip: ts for ip, ts in dst_map.items() if ts >= cutoff
        }
