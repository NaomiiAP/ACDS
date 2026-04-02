"""
unsupervised.py — Autoencoder (PyTorch) and IsolationForest (sklearn).

The Autoencoder is trained on benign traffic only; reconstruction error
serves as the anomaly score, normalized to [0, 1].
IsolationForest provides a complementary density-based anomaly signal.
"""

import logging
import os
from typing import Optional

import joblib
import numpy as np
import torch
import torch.nn as nn
from sklearn.ensemble import IsolationForest as SklearnIsolationForest

log = logging.getLogger("ml_service.models.unsupervised")

NUM_FEATURES = 14


# ---------------------------------------------------------------------------
# Autoencoder
# ---------------------------------------------------------------------------

class _AutoencoderNet(nn.Module):
    """Symmetric autoencoder: 14 -> 8 -> 4 -> 8 -> 14."""

    def __init__(self, input_dim: int = NUM_FEATURES):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 8),
            nn.ReLU(),
            nn.Linear(8, 4),
            nn.ReLU(),
        )
        self.decoder = nn.Sequential(
            nn.Linear(4, 8),
            nn.ReLU(),
            nn.Linear(8, input_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        z = self.encoder(x)
        return self.decoder(z)


class AutoencoderModel:
    """Autoencoder anomaly detector trained on benign traffic only."""

    def __init__(
        self,
        input_dim: int = NUM_FEATURES,
        epochs: int = 50,
        batch_size: int = 256,
        learning_rate: float = 1e-3,
        device: Optional[str] = None,
    ):
        self.input_dim = input_dim
        self.epochs = epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.net = _AutoencoderNet(input_dim).to(self.device)
        self._threshold: float = 0.0  # set during training
        self._max_error: float = 1.0  # for normalization
        self._is_fitted = False

    def train(self, X_benign: np.ndarray) -> "AutoencoderModel":
        """Train on benign-only data. X_benign shape: (n_samples, 14)."""
        log.info("Training Autoencoder on %d benign samples", X_benign.shape[0])
        dataset = torch.utils.data.TensorDataset(
            torch.tensor(X_benign, dtype=torch.float32)
        )
        loader = torch.utils.data.DataLoader(
            dataset, batch_size=self.batch_size, shuffle=True
        )

        optimizer = torch.optim.Adam(self.net.parameters(), lr=self.learning_rate)
        criterion = nn.MSELoss()

        self.net.train()
        for epoch in range(1, self.epochs + 1):
            epoch_loss = 0.0
            for (batch,) in loader:
                batch = batch.to(self.device)
                recon = self.net(batch)
                loss = criterion(recon, batch)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item() * batch.size(0)
            avg_loss = epoch_loss / len(dataset)
            if epoch % 10 == 0 or epoch == 1:
                log.info("  Epoch %3d/%d  loss=%.6f", epoch, self.epochs, avg_loss)

        # Compute threshold as 95th-percentile reconstruction error on training set
        errors = self._compute_errors(X_benign)
        self._threshold = float(np.percentile(errors, 95))
        self._max_error = float(np.max(errors)) + 1e-8
        self._is_fitted = True
        log.info("Autoencoder training complete. threshold=%.6f", self._threshold)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Return anomaly scores normalized to [0, 1]. Higher = more anomalous."""
        if not self._is_fitted:
            raise RuntimeError("AutoencoderModel is not fitted yet.")
        errors = self._compute_errors(X)
        # Normalize: clip and scale to [0, 1]
        scores = np.clip(errors / self._max_error, 0.0, 1.0)
        return scores

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        state = {
            "net_state": self.net.state_dict(),
            "threshold": self._threshold,
            "max_error": self._max_error,
            "input_dim": self.input_dim,
        }
        torch.save(state, path)
        log.info("Autoencoder saved to %s", path)

    def load(self, path: str) -> "AutoencoderModel":
        state = torch.load(path, map_location=self.device, weights_only=False)
        self.input_dim = state["input_dim"]
        self.net = _AutoencoderNet(self.input_dim).to(self.device)
        self.net.load_state_dict(state["net_state"])
        self._threshold = state["threshold"]
        self._max_error = state["max_error"]
        self._is_fitted = True
        log.info("Autoencoder loaded from %s", path)
        return self

    def get_pytorch_model(self) -> _AutoencoderNet:
        """Return the underlying PyTorch module (for ONNX export)."""
        return self.net

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _compute_errors(self, X: np.ndarray) -> np.ndarray:
        self.net.eval()
        with torch.no_grad():
            t = torch.tensor(X, dtype=torch.float32).to(self.device)
            recon = self.net(t)
            mse = torch.mean((t - recon) ** 2, dim=1)
        return mse.cpu().numpy()


# ---------------------------------------------------------------------------
# IsolationForest
# ---------------------------------------------------------------------------

class IsolationForestModel:
    """Wrapper around sklearn IsolationForest."""

    def __init__(
        self,
        contamination: float = 0.05,
        n_estimators: int = 200,
        random_state: int = 42,
    ):
        self.model = SklearnIsolationForest(
            contamination=contamination,
            n_estimators=n_estimators,
            random_state=random_state,
            n_jobs=-1,
        )
        self._is_fitted = False

    def train(self, X: np.ndarray) -> "IsolationForestModel":
        """Train on full dataset (benign + attack)."""
        log.info("Training IsolationForest on %d samples", X.shape[0])
        self.model.fit(X)
        self._is_fitted = True
        log.info("IsolationForest training complete.")
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Return anomaly scores in [0, 1]. Higher = more anomalous."""
        if not self._is_fitted:
            raise RuntimeError("IsolationForestModel is not fitted yet.")
        # decision_function returns negative for anomalies
        raw = self.model.decision_function(X)
        # Negate and normalize to [0, 1]
        shifted = -raw
        mn, mx = shifted.min(), shifted.max()
        if mx - mn < 1e-8:
            return np.zeros(len(X))
        scores = (shifted - mn) / (mx - mn)
        return scores

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump(self.model, path)
        log.info("IsolationForest saved to %s", path)

    def load(self, path: str) -> "IsolationForestModel":
        self.model = joblib.load(path)
        self._is_fitted = True
        log.info("IsolationForest loaded from %s", path)
        return self
