"""
ensemble.py — Weighted ensemble of supervised and unsupervised models.

Combines XGBoost, RandomForest, Autoencoder, and IsolationForest scores
into a single ensemble prediction using configurable weights.
"""

import logging
from typing import Any, Dict, Optional

import numpy as np

log = logging.getLogger("ml_service.models.ensemble")

# Default ensemble weights
DEFAULT_WEIGHTS = {
    "xgboost": 0.35,
    "random_forest": 0.25,
    "autoencoder": 0.25,
    "isolation_forest": 0.15,
}

# Attack-type labels for multi-class mapping
ATTACK_LABELS = {
    0: "Benign",
    1: "DDoS",
    2: "PortScan",
    3: "BruteForce",
    4: "Botnet",
    5: "Infiltration",
    6: "WebAttack",
    7: "DoS",
    8: "C2",
    9: "Exfiltration",
}


class EnsembleModel:
    """Weighted combination of four model scores."""

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        attack_labels: Optional[Dict[int, str]] = None,
    ):
        self.weights = weights or DEFAULT_WEIGHTS.copy()
        self.attack_labels = attack_labels or ATTACK_LABELS.copy()
        # Normalize weights so they sum to 1
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}

    def predict(
        self,
        xgb_score: float,
        rf_score: float,
        ae_score: float,
        iforest_score: float,
        xgb_class: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Combine individual model scores into an ensemble prediction.

        Parameters
        ----------
        xgb_score    : XGBoost P(attack)
        rf_score     : RandomForest P(attack)
        ae_score     : Autoencoder anomaly score [0,1]
        iforest_score: IsolationForest anomaly score [0,1]
        xgb_class    : Optional multi-class prediction from XGBoost

        Returns
        -------
        dict with ensemble_score, supervised_score, unsupervised_score, predicted_label
        """
        supervised_score = (
            self.weights["xgboost"] * xgb_score
            + self.weights["random_forest"] * rf_score
        ) / (self.weights["xgboost"] + self.weights["random_forest"])

        unsupervised_score = (
            self.weights["autoencoder"] * ae_score
            + self.weights["isolation_forest"] * iforest_score
        ) / (self.weights["autoencoder"] + self.weights["isolation_forest"])

        ensemble_score = (
            self.weights["xgboost"] * xgb_score
            + self.weights["random_forest"] * rf_score
            + self.weights["autoencoder"] * ae_score
            + self.weights["isolation_forest"] * iforest_score
        )

        # Determine predicted label
        if xgb_class is not None and xgb_class in self.attack_labels:
            predicted_label = self.attack_labels[xgb_class]
        elif ensemble_score >= 0.5:
            predicted_label = "Attack"
        else:
            predicted_label = "Benign"

        return {
            "ensemble_score": round(float(ensemble_score), 4),
            "supervised_score": round(float(supervised_score), 4),
            "unsupervised_score": round(float(unsupervised_score), 4),
            "predicted_label": predicted_label,
        }

    def predict_batch(
        self,
        xgb_scores: np.ndarray,
        rf_scores: np.ndarray,
        ae_scores: np.ndarray,
        iforest_scores: np.ndarray,
    ) -> np.ndarray:
        """Vectorized ensemble scoring. Returns ensemble_score array."""
        return (
            self.weights["xgboost"] * xgb_scores
            + self.weights["random_forest"] * rf_scores
            + self.weights["autoencoder"] * ae_scores
            + self.weights["isolation_forest"] * iforest_scores
        )
