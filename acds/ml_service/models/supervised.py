"""
supervised.py — XGBoost and RandomForest classifier wrappers.

Both models accept a feature matrix X and label vector y for training,
and return probability scores (0-1) during prediction.
Persistence is handled via joblib.
"""

import logging
import os
from typing import Optional

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier

log = logging.getLogger("ml_service.models.supervised")

# ---------------------------------------------------------------------------
# Feature names (14-element vector)
# ---------------------------------------------------------------------------

FEATURE_NAMES = [
    "connection_frequency",
    "avg_packet_size",
    "entropy",
    "burst_rate",
    "inter_arrival_time",
    "tls_fingerprint_encoded",
    "window_10s_count",
    "window_30s_count",
    "window_60s_count",
    "window_avg_entropy",
    "window_max_burst",
    "window_unique_dst_ports",
    "process_connection_count",
    "container_unique_dst_ips",
]


# ---------------------------------------------------------------------------
# XGBoost wrapper
# ---------------------------------------------------------------------------

class XGBoostModel:
    """Wrapper around XGBClassifier with train / predict / save / load."""

    def __init__(
        self,
        n_estimators: int = 300,
        max_depth: int = 8,
        learning_rate: float = 0.05,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        random_state: int = 42,
    ):
        self.model = XGBClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            subsample=subsample,
            colsample_bytree=colsample_bytree,
            use_label_encoder=False,
            eval_metric="logloss",
            random_state=random_state,
            n_jobs=-1,
        )
        self._is_fitted = False

    def train(self, X: np.ndarray, y: np.ndarray) -> "XGBoostModel":
        """Train on feature matrix X and binary labels y."""
        log.info("Training XGBoost  (%d samples, %d features)", X.shape[0], X.shape[1])
        self.model.fit(X, y)
        self._is_fitted = True
        log.info("XGBoost training complete.")
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return P(attack) for each row — shape (n_samples,)."""
        if not self._is_fitted:
            raise RuntimeError("XGBoostModel is not fitted yet.")
        proba = self.model.predict_proba(X)
        # Column 1 = P(attack)
        return proba[:, 1] if proba.ndim == 2 else proba

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Hard prediction (0 or 1)."""
        if not self._is_fitted:
            raise RuntimeError("XGBoostModel is not fitted yet.")
        return self.model.predict(X)

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump(self.model, path)
        log.info("XGBoost model saved to %s", path)

    def load(self, path: str) -> "XGBoostModel":
        self.model = joblib.load(path)
        self._is_fitted = True
        log.info("XGBoost model loaded from %s", path)
        return self


# ---------------------------------------------------------------------------
# RandomForest wrapper
# ---------------------------------------------------------------------------

class RandomForestModel:
    """Wrapper around sklearn RandomForestClassifier."""

    def __init__(
        self,
        n_estimators: int = 200,
        max_depth: int = 12,
        min_samples_split: int = 5,
        random_state: int = 42,
    ):
        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            random_state=random_state,
            n_jobs=-1,
        )
        self._is_fitted = False

    def train(self, X: np.ndarray, y: np.ndarray) -> "RandomForestModel":
        log.info("Training RandomForest  (%d samples, %d features)", X.shape[0], X.shape[1])
        self.model.fit(X, y)
        self._is_fitted = True
        log.info("RandomForest training complete.")
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError("RandomForestModel is not fitted yet.")
        proba = self.model.predict_proba(X)
        return proba[:, 1] if proba.ndim == 2 else proba

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError("RandomForestModel is not fitted yet.")
        return self.model.predict(X)

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump(self.model, path)
        log.info("RandomForest model saved to %s", path)

    def load(self, path: str) -> "RandomForestModel":
        self.model = joblib.load(path)
        self._is_fitted = True
        log.info("RandomForest model loaded from %s", path)
        return self
