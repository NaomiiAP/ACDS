"""
threshold_manager.py — Dynamic threshold management for ML alerts.

Tracks a rolling window of ensemble scores and adjusts the alert threshold
to maintain a target false-positive budget.
"""

import logging
import time
from collections import deque
from typing import Optional

import numpy as np

log = logging.getLogger("ml_service.inference.threshold_manager")


class ThresholdManager:
    """
    Maintains a dynamic threshold based on a rolling window of scores
    and a configurable false-positive budget.
    """

    def __init__(
        self,
        fp_budget: float = 0.01,
        window_size: int = 10000,
        min_samples: int = 100,
        default_threshold: float = 0.65,
        update_interval: float = 60.0,
    ):
        """
        Parameters
        ----------
        fp_budget         : Target false-positive rate (default 1%)
        window_size       : Maximum number of scores in the rolling window
        min_samples       : Minimum samples before dynamic threshold kicks in
        default_threshold : Threshold used until min_samples is reached
        update_interval   : Seconds between threshold recalculations
        """
        self.fp_budget = fp_budget
        self.window_size = window_size
        self.min_samples = min_samples
        self.default_threshold = default_threshold
        self.update_interval = update_interval

        self._scores: deque = deque(maxlen=window_size)
        self._current_threshold: float = default_threshold
        self._last_update: float = 0.0
        self._alert_count: int = 0
        self._total_count: int = 0

    @property
    def threshold(self) -> float:
        """Current alert threshold."""
        return self._current_threshold

    def add_score(self, score: float) -> None:
        """Add a new ensemble score to the rolling window."""
        self._scores.append(score)
        self._total_count += 1
        if score >= self._current_threshold:
            self._alert_count += 1

        # Periodically recalculate
        now = time.time()
        if now - self._last_update >= self.update_interval:
            self._recalculate()
            self._last_update = now

    def should_alert(self, score: float) -> bool:
        """Return True if the score exceeds the current threshold."""
        return score >= self._current_threshold

    def get_risk_level(self, score: float) -> str:
        """Map ensemble score to a risk level string."""
        if score >= 0.85:
            return "critical"
        elif score >= 0.70:
            return "high"
        elif score >= 0.50:
            return "medium"
        elif score >= 0.30:
            return "low"
        else:
            return "info"

    def get_stats(self) -> dict:
        """Return current threshold statistics."""
        return {
            "current_threshold": round(self._current_threshold, 4),
            "fp_budget": self.fp_budget,
            "window_size": len(self._scores),
            "total_scored": self._total_count,
            "alert_count": self._alert_count,
            "alert_rate": round(self._alert_count / max(self._total_count, 1), 4),
        }

    def force_update(self) -> float:
        """Force a threshold recalculation and return the new threshold."""
        self._recalculate()
        return self._current_threshold

    def set_threshold(self, value: float) -> None:
        """Manually override the threshold."""
        self._current_threshold = value
        log.info("Threshold manually set to %.4f", value)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _recalculate(self) -> None:
        """Recalculate threshold based on rolling window and FP budget."""
        n = len(self._scores)
        if n < self.min_samples:
            return

        scores_arr = np.array(self._scores)
        # Set threshold at the (1 - fp_budget) percentile
        # This means only fp_budget fraction of scores would trigger alerts
        new_threshold = float(np.percentile(scores_arr, (1.0 - self.fp_budget) * 100))

        # Clamp to reasonable range
        new_threshold = max(0.3, min(0.95, new_threshold))

        if abs(new_threshold - self._current_threshold) > 0.01:
            log.info(
                "Threshold updated: %.4f -> %.4f (window=%d, fp_budget=%.3f)",
                self._current_threshold,
                new_threshold,
                n,
                self.fp_budget,
            )
            self._current_threshold = new_threshold

        # Reset alert counters
        self._alert_count = 0
        self._total_count = 0
