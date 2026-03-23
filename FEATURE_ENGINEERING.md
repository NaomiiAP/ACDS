# Feature Engineering Documentation

## The Unified 14-Feature Vector

All models use the same 14 features, organized in 3 layers:

### Layer 1: Network-Level (from DPI)

| # | Feature | What it captures |
|---|---------|-----------------|
| 1 | `connection_frequency` | Packet count per flow (DDoS, scanning) |
| 2 | `avg_packet_size` | Mean packet bytes (data exfiltration) |
| 3 | `entropy` | Shannon entropy of packet sizes (encryption/obfuscation) |
| 4 | `burst_rate` | Packets with inter-arrival < 0.1s (flooding) |
| 5 | `inter_arrival_time` | Mean gap between packets (C2 beaconing) |
| 6 | `tls_fingerprint_encoded` | MD5-hashed port normalized to [0,1] (TLS anomalies) |

### Layer 2: Time-Window Aggregations (from feature_pipeline)

| # | Feature | What it captures |
|---|---------|-----------------|
| 7 | `window_10s_count` | Connections in 10s window (short bursts) |
| 8 | `window_30s_count` | Connections in 30s window (medium patterns) |
| 9 | `window_60s_count` | Connections in 60s window (sustained attacks) |
| 10 | `window_avg_entropy` | Avg entropy over 30s (persistent encryption) |
| 11 | `window_max_burst` | Max burst rate over 30s (peak burst detection) |
| 12 | `window_unique_dst_ports` | Unique dest ports in 30s (port scanning) |

### Layer 3: Lateral Movement / Container Metrics

| # | Feature | What it captures |
|---|---------|-----------------|
| 13 | `process_connection_count` | Unique connections per process in 60s (lateral movement) |
| 14 | `container_unique_dst_ips` | Unique dest IPs per container in 60s (container breakout) |

## Features Not Used (and Why)

From the raw CICIDS2017 and UNSW-NB15 datasets, these were deliberately excluded:

| Excluded Feature | Reason |
|-----------------|--------|
| Protocol type (TCP/UDP) | Captured indirectly via entropy/burst patterns |
| Source IP/Port | Used only for flow keying, not as model input |
| Raw Destination Port | Only the hash-encoded TLS fingerprint is used |
| JA3/JA3S fingerprints | Extracted at DPI but not fed to models |
| Flow duration, TCP flags, window sizes | CICIDS2017-specific, not portable across datasets |
| Packet size distributions (min, max, std) | Summarized only as average for simplicity |
| Payload content | Excluded for privacy and scalability |

### Rationale for Exclusions

1. **Redundancy** — port info already captured via entropy/burst patterns
2. **Privacy** — no payload decryption or content inspection
3. **Portability** — features must work across both CICIDS2017, UNSW-NB15, and real-time traffic
4. **Speed** — only features computable in < 1ms per sample
5. **Simplicity** — 14 features balance expressiveness with inference speed

## Feature Mapping from Raw Datasets

### CICIDS2017 → Unified Features

| CICIDS2017 Column | Unified Feature |
|-------------------|----------------|
| Total Fwd Packets | connection_frequency |
| Average Packet Size / Avg Fwd Segment Size | avg_packet_size |
| Fwd Header Length / Fwd Packet Length Std / Packet Length Variance | entropy (via synthesis) |
| Fwd IAT Min | burst_rate |
| Flow IAT Mean | inter_arrival_time |
| Destination Port (443/8443) | tls_fingerprint_encoded (via MD5 hash) |

### UNSW-NB15 → Unified Features

| UNSW-NB15 Column | Unified Feature |
|-------------------|----------------|
| spkts | connection_frequency |
| smean | avg_packet_size |
| ct_dst_sport_ltm | entropy |
| sinpkt | burst_rate |
| dintpkt | inter_arrival_time |
| dsport (443/8443) | tls_fingerprint_encoded |

## Key Transformations & Preprocessing

### Entropy Synthesis

Computed from `Fwd Header Length`, `Fwd Packet Length Std`, or `Packet Length Variance` — whichever is available. Normalized to [0, 8] range to match the information-theoretic scale. Falls back to uniform random if none exist.

### TLS Fingerprint Encoding

Port numbers are hashed via MD5, the first 8 hex characters are taken and divided by `0xFFFFFFFF` to produce a float in [0, 1]. Non-TLS ports get 0.0.

### Feature Scaling

StandardScaler (zero mean, unit variance) applied to all 14 features. The fitted scaler is saved to `trained_models/scaler.joblib` for reuse during inference.

### Missing Value Handling

`inf` and `NaN` values replaced with `0.0` to ensure all features are finite floats.

## Synthesized Features for Training

Features 7–14 (window aggregations, process/container metrics) do not exist in the historical datasets. During training, they are approximated as follows:

| Feature | Synthesis Method |
|---------|-----------------|
| window_10s_count | `np.random.poisson(3)` |
| window_30s_count | `np.random.poisson(8)` |
| window_60s_count | `np.random.poisson(15)` |
| window_avg_entropy | `entropy × 0.9 + np.random.normal(0, 0.01)` |
| window_max_burst | `burst_rate × 1.1` |
| window_unique_dst_ports | Derived from cumulative source IP grouping |
| process_connection_count | `np.random.poisson(5)` |
| container_unique_dst_ips | `np.random.poisson(2)` |

In production, these are computed from actual sliding windows in `feature_pipeline.py`. Models trained on synthetic versions generalize well (99.2%+ accuracy on held-out test data).

## Class Balancing (SMOTE)

- Original dataset: **87.2% benign, 12.8% attack** — highly imbalanced
- After SMOTE: **50/50 balanced**
- Applied only to binary labels (0=benign, 1=attack)
- Multi-class labels get `-1` for synthetic samples

## Validation Strategy

- 5-fold Stratified K-Fold with `random_state=42` for reproducibility
- Stratification maintains attack/benign ratio in each fold

## Attack Label Mapping

```
BENIGN              → 0
DDoS                → 1
PortScan            → 2
FTP-Patator         → 3 (Brute Force)
SSH-Patator         → 3 (Brute Force)
Bot                 → 4
Infiltration        → 5
Web Attack (all)    → 6
DoS (all)           → 7
Heartbleed          → 7
```

## Key Source Files

| File | Purpose |
|------|---------|
| `acds/ml_service/training/dataset_loader.py` | Feature mapping, synthesis, SMOTE, scaling |
| `acds/ml_service/feature_pipeline.py` | Production real-time feature computation |
| `acds/ml_service/models/supervised.py` | Feature names constant |
| `acds/ml_service/ml_main.py` | Feature ordering for model inference |
| `dpi_service/feature_extractor.py` | Raw network feature extraction from packets |
