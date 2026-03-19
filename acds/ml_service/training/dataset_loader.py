"""
dataset_loader.py — Load CICIDS2017 and UNSW-NB15 datasets into a unified
14-feature vector, apply SMOTE for class balancing, and return stratified
train/test splits.
"""

import hashlib
import logging
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

log = logging.getLogger("ml_service.training.dataset_loader")

# ---------------------------------------------------------------------------
# Unified feature names (14 total)
# ---------------------------------------------------------------------------

UNIFIED_FEATURES = [
    "connection_frequency",       # 1
    "avg_packet_size",            # 2
    "entropy",                    # 3
    "burst_rate",                 # 4
    "inter_arrival_time",         # 5
    "tls_fingerprint_encoded",    # 6
    "window_10s_count",           # 7
    "window_30s_count",           # 8
    "window_60s_count",           # 9
    "window_avg_entropy",         # 10
    "window_max_burst",           # 11
    "window_unique_dst_ports",    # 12
    "process_connection_count",   # 13
    "container_unique_dst_ips",   # 14
]

# ---------------------------------------------------------------------------
# CICIDS2017 column mappings
# ---------------------------------------------------------------------------

CICIDS_LABEL_COL = " Label"
CICIDS_ATTACK_MAP = {
    "BENIGN": 0,
    "DDoS": 1,
    "PortScan": 2,
    "FTP-Patator": 3,
    "SSH-Patator": 3,
    "Bot": 4,
    "Infiltration": 5,
    "Web Attack": 6,
    "Web Attack - Brute Force": 6,
    "Web Attack - XSS": 6,
    "Web Attack - Sql Injection": 6,
    "DoS Hulk": 7,
    "DoS GoldenEye": 7,
    "DoS slowloris": 7,
    "DoS Slowhttptest": 7,
    "Heartbleed": 7,
}


def _hash_port(port: int) -> float:
    """Encode a port number as a float in [0, 1] using a hash."""
    h = hashlib.md5(str(port).encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def load_cicids2017(data_dir: str) -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Load all CICIDS2017 CSV files from data_dir.

    Returns
    -------
    X : DataFrame with 14 unified features
    y_binary : Series (0=benign, 1=attack)
    y_multi  : Series (multi-class attack label)
    """
    csv_files = sorted(
        [os.path.join(data_dir, f) for f in os.listdir(data_dir) if f.endswith(".csv")]
    )
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")

    frames = []
    for fp in csv_files:
        log.info("Loading CICIDS2017 file: %s", fp)
        df = pd.read_csv(fp, low_memory=False, encoding="utf-8")
        frames.append(df)
    raw = pd.concat(frames, ignore_index=True)

    # Clean column names
    raw.columns = raw.columns.str.strip()

    # Map labels
    label_col = "Label"
    if label_col not in raw.columns:
        # Try alternate column name
        for c in raw.columns:
            if "label" in c.lower():
                label_col = c
                break

    raw["attack_type"] = raw[label_col].map(
        lambda x: CICIDS_ATTACK_MAP.get(str(x).strip(), 0)
    )
    raw["binary_label"] = (raw["attack_type"] > 0).astype(int)

    # Build unified features
    X = pd.DataFrame()
    X["connection_frequency"] = raw.get("Total Fwd Packets", pd.Series(0, index=raw.index)).astype(float)
    X["avg_packet_size"] = raw.get("Average Packet Size", raw.get("Avg Fwd Segment Size", pd.Series(0, index=raw.index))).astype(float)
    X["entropy"] = _synthesize_entropy(raw)
    X["burst_rate"] = raw.get("Fwd IAT Min", pd.Series(0, index=raw.index)).astype(float)
    X["inter_arrival_time"] = raw.get("Flow IAT Mean", pd.Series(0, index=raw.index)).astype(float)
    X["tls_fingerprint_encoded"] = raw.get("Destination Port", pd.Series(0, index=raw.index)).apply(
        lambda p: _hash_port(int(p)) if int(p) == 443 or int(p) == 8443 else 0.0
    )

    # Time-window features: synthesize by grouping flows by source IP
    src_ip_col = None
    for candidate in ["Source IP", "Src IP", "src_ip"]:
        if candidate in raw.columns:
            src_ip_col = candidate
            break

    if src_ip_col:
        src_counts = raw.groupby(src_ip_col).cumcount()
        X["window_10s_count"] = (src_counts % 20).astype(float)
        X["window_30s_count"] = (src_counts % 50).astype(float)
        X["window_60s_count"] = (src_counts % 100).astype(float)
    else:
        X["window_10s_count"] = np.random.poisson(3, size=len(raw)).astype(float)
        X["window_30s_count"] = np.random.poisson(8, size=len(raw)).astype(float)
        X["window_60s_count"] = np.random.poisson(15, size=len(raw)).astype(float)

    X["window_avg_entropy"] = X["entropy"] * 0.9 + np.random.normal(0, 0.01, len(raw))
    X["window_max_burst"] = X["burst_rate"] * 1.1
    X["window_unique_dst_ports"] = raw.get("Destination Port", pd.Series(1, index=raw.index)).astype(float)

    # Lateral movement indicators (synthesized)
    X["process_connection_count"] = np.random.poisson(5, size=len(raw)).astype(float)
    X["container_unique_dst_ips"] = np.random.poisson(2, size=len(raw)).astype(float)

    # Clean infinities and NaN
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    return X, raw["binary_label"], raw["attack_type"]


def _synthesize_entropy(raw: pd.DataFrame) -> pd.Series:
    """Compute or approximate entropy from packet size statistics."""
    for col in ["Fwd Header Length", "Fwd Packet Length Std", "Packet Length Variance"]:
        if col in raw.columns:
            vals = raw[col].astype(float).clip(lower=0)
            # Normalize to [0, ~8] entropy range
            mx = vals.max()
            if mx > 0:
                return (vals / mx) * 8.0
    return pd.Series(np.random.uniform(0, 4, len(raw)))


# ---------------------------------------------------------------------------
# UNSW-NB15
# ---------------------------------------------------------------------------

UNSW_ATTACK_MAP = {
    "Normal": 0,
    "Fuzzers": 1,
    "Analysis": 2,
    "Backdoor": 3,
    "Backdoors": 3,
    "DoS": 7,
    "Exploits": 5,
    "Generic": 1,
    "Reconnaissance": 2,
    "Shellcode": 5,
    "Worms": 4,
}


def load_unsw_nb15(data_dir: str) -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Load UNSW-NB15 CSV files from data_dir.

    Returns same format as load_cicids2017.
    """
    csv_files = sorted(
        [os.path.join(data_dir, f) for f in os.listdir(data_dir) if f.endswith(".csv")]
    )
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")

    frames = []
    for fp in csv_files:
        log.info("Loading UNSW-NB15 file: %s", fp)
        df = pd.read_csv(fp, low_memory=False, encoding="utf-8")
        frames.append(df)
    raw = pd.concat(frames, ignore_index=True)
    raw.columns = raw.columns.str.strip()

    # Labels
    label_col = "attack_cat"
    if label_col not in raw.columns:
        for c in raw.columns:
            if "attack" in c.lower() and "cat" in c.lower():
                label_col = c
                break

    if label_col in raw.columns:
        raw["attack_type"] = raw[label_col].fillna("Normal").map(
            lambda x: UNSW_ATTACK_MAP.get(str(x).strip(), 0)
        )
    else:
        raw["attack_type"] = raw.get("label", pd.Series(0, index=raw.index)).astype(int)

    raw["binary_label"] = (raw["attack_type"] > 0).astype(int)

    # Build unified features
    X = pd.DataFrame()
    X["connection_frequency"] = raw.get("spkts", raw.get("Spkts", pd.Series(0, index=raw.index))).astype(float)
    X["avg_packet_size"] = raw.get("smean", raw.get("Smean", pd.Series(0, index=raw.index))).astype(float)
    X["entropy"] = raw.get("ct_dst_sport_ltm", pd.Series(np.random.uniform(0, 4, len(raw)))).astype(float)
    X["burst_rate"] = raw.get("sinpkt", raw.get("Sinpkt", pd.Series(0, index=raw.index))).astype(float)
    X["inter_arrival_time"] = raw.get("dintpkt", raw.get("Dintpkt", pd.Series(0, index=raw.index))).astype(float)
    X["tls_fingerprint_encoded"] = raw.get("dsport", raw.get("Dsport", pd.Series(0, index=raw.index))).apply(
        lambda p: _hash_port(int(p)) if int(p) in (443, 8443) else 0.0
    )

    # Synthesized window features
    X["window_10s_count"] = np.random.poisson(3, size=len(raw)).astype(float)
    X["window_30s_count"] = np.random.poisson(8, size=len(raw)).astype(float)
    X["window_60s_count"] = np.random.poisson(15, size=len(raw)).astype(float)
    X["window_avg_entropy"] = X["entropy"] * 0.9
    X["window_max_burst"] = X["burst_rate"] * 1.1
    X["window_unique_dst_ports"] = raw.get("ct_dst_ltm", pd.Series(1, index=raw.index)).astype(float)
    X["process_connection_count"] = np.random.poisson(5, size=len(raw)).astype(float)
    X["container_unique_dst_ips"] = np.random.poisson(2, size=len(raw)).astype(float)

    X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return X, raw["binary_label"], raw["attack_type"]


# ---------------------------------------------------------------------------
# Unified loader with SMOTE + StratifiedKFold
# ---------------------------------------------------------------------------

def load_dataset(
    cicids_dir: Optional[str] = None,
    unsw_dir: Optional[str] = None,
    apply_smote: bool = True,
    n_folds: int = 5,
    scale: bool = True,
) -> Dict:
    """
    Load and combine datasets, apply SMOTE, return stratified k-fold splits.

    Returns
    -------
    dict with keys:
        X, y_binary, y_multi : full arrays (after SMOTE if enabled)
        folds : list of (train_idx, test_idx) tuples
        scaler : fitted StandardScaler (or None)
        feature_names : list of str
    """
    X_parts, yb_parts, ym_parts = [], [], []

    if cicids_dir and os.path.isdir(cicids_dir):
        X_c, yb_c, ym_c = load_cicids2017(cicids_dir)
        X_parts.append(X_c)
        yb_parts.append(yb_c)
        ym_parts.append(ym_c)
        log.info("CICIDS2017: %d samples loaded", len(X_c))

    if unsw_dir and os.path.isdir(unsw_dir):
        X_u, yb_u, ym_u = load_unsw_nb15(unsw_dir)
        X_parts.append(X_u)
        yb_parts.append(yb_u)
        ym_parts.append(ym_u)
        log.info("UNSW-NB15: %d samples loaded", len(X_u))

    if not X_parts:
        raise ValueError("No dataset directories provided or found.")

    X = pd.concat(X_parts, ignore_index=True).values.astype(np.float32)
    y_binary = pd.concat(yb_parts, ignore_index=True).values.astype(np.int64)
    y_multi = pd.concat(ym_parts, ignore_index=True).values.astype(np.int64)

    log.info(
        "Combined dataset: %d samples, %d features, attack ratio=%.2f%%",
        X.shape[0], X.shape[1], y_binary.mean() * 100,
    )

    # Scale features
    scaler = None
    if scale:
        scaler = StandardScaler()
        X = scaler.fit_transform(X)

    # Apply SMOTE for class balancing
    if apply_smote:
        log.info("Applying SMOTE for class balancing...")
        sm = SMOTE(random_state=42)
        X, y_binary = sm.fit_resample(X, y_binary)
        # y_multi cannot be resampled by SMOTE directly; extend with -1
        extra = len(X) - len(y_multi)
        if extra > 0:
            y_multi = np.concatenate([y_multi, np.full(extra, -1, dtype=np.int64)])
        log.info("After SMOTE: %d samples, attack ratio=%.2f%%", len(X), y_binary.mean() * 100)

    # Stratified K-Fold
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
    folds = list(skf.split(X, y_binary))

    return {
        "X": X.astype(np.float32),
        "y_binary": y_binary,
        "y_multi": y_multi,
        "folds": folds,
        "scaler": scaler,
        "feature_names": UNIFIED_FEATURES,
    }
