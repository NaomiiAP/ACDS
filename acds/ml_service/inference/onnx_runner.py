"""
onnx_runner.py — ONNX Runtime inference engine for all four model types.

Loads ONNX models via onnxruntime.InferenceSession and provides a unified
interface for scoring feature vectors.
"""

import logging
import os
from typing import Dict, List, Optional

import numpy as np

log = logging.getLogger("ml_service.inference.onnx_runner")


class ONNXRunner:
    """Load and run inference on ONNX models."""

    def __init__(self):
        self._sessions: Dict[str, "onnxruntime.InferenceSession"] = {}
        self._input_names: Dict[str, str] = {}
        self._output_names: Dict[str, List[str]] = {}

    def load_model(self, name: str, onnx_path: str) -> None:
        """Load an ONNX model from disk.

        Parameters
        ----------
        name      : logical name (e.g. "xgboost", "autoencoder")
        onnx_path : path to .onnx file
        """
        import onnxruntime as ort

        if not os.path.exists(onnx_path):
            raise FileNotFoundError(f"ONNX model not found: {onnx_path}")

        providers = ["CPUExecutionProvider"]
        if ort.get_available_providers() and "CUDAExecutionProvider" in ort.get_available_providers():
            providers.insert(0, "CUDAExecutionProvider")

        session = ort.InferenceSession(onnx_path, providers=providers)
        self._sessions[name] = session
        self._input_names[name] = session.get_inputs()[0].name
        self._output_names[name] = [o.name for o in session.get_outputs()]
        log.info("Loaded ONNX model '%s' from %s (outputs: %s)", name, onnx_path, self._output_names[name])

    def is_loaded(self, name: str) -> bool:
        return name in self._sessions

    def predict(self, name: str, X: np.ndarray) -> np.ndarray:
        """
        Run inference on a loaded ONNX model.

        Parameters
        ----------
        name : model name
        X    : feature array, shape (n_samples, n_features), dtype float32

        Returns
        -------
        For classifiers: probability scores shape (n_samples,)
        For autoencoder: reconstruction output shape (n_samples, n_features)
        """
        if name not in self._sessions:
            raise KeyError(f"Model '{name}' is not loaded. Call load_model() first.")

        session = self._sessions[name]
        input_name = self._input_names[name]

        if X.dtype != np.float32:
            X = X.astype(np.float32)

        if X.ndim == 1:
            X = X.reshape(1, -1)

        results = session.run(None, {input_name: X})

        # Classifiers typically have two outputs: labels and probabilities
        if len(results) >= 2 and isinstance(results[1], (list, np.ndarray)):
            proba = results[1]
            # Handle list-of-dicts format from some sklearn converters
            if isinstance(proba, list) and len(proba) > 0 and isinstance(proba[0], dict):
                return np.array([d.get(1, 0.0) for d in proba], dtype=np.float32)
            proba = np.array(proba, dtype=np.float32)
            if proba.ndim == 2 and proba.shape[1] >= 2:
                return proba[:, 1]
            return proba.flatten()

        # Single output (autoencoder reconstruction)
        return np.array(results[0], dtype=np.float32)

    def predict_autoencoder_score(self, name: str, X: np.ndarray) -> np.ndarray:
        """
        Run autoencoder inference and compute reconstruction error as anomaly score.

        Returns scores normalized to [0, 1].
        """
        if X.dtype != np.float32:
            X = X.astype(np.float32)
        if X.ndim == 1:
            X = X.reshape(1, -1)

        reconstruction = self.predict(name, X)
        mse = np.mean((X - reconstruction) ** 2, axis=1)
        # Normalize to [0, 1] using a sigmoid-like transform
        scores = 1.0 / (1.0 + np.exp(-10 * (mse - np.median(mse))))
        return scores.astype(np.float32)

    def list_models(self) -> List[str]:
        """Return names of all loaded models."""
        return list(self._sessions.keys())

    def unload_model(self, name: str) -> None:
        """Unload a model from memory."""
        self._sessions.pop(name, None)
        self._input_names.pop(name, None)
        self._output_names.pop(name, None)
        log.info("Unloaded ONNX model '%s'", name)
