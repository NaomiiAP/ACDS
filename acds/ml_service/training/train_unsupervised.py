"""
train_unsupervised.py — Train Autoencoder and IsolationForest.

The Autoencoder is trained on benign-only traffic.
The IsolationForest is trained on the full dataset.

Usage:
    python -m ml_service.training.train_unsupervised \
        --cicids-dir /path/to/cicids2017 \
        --output-dir ./trained_models
"""

import argparse
import logging
import os
import sys

import numpy as np
from sklearn.metrics import (
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)

from ml_service.training.dataset_loader import load_dataset
from ml_service.models.unsupervised import AutoencoderModel, IsolationForestModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [TRAIN-UNS] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("train_unsupervised")


def train_and_evaluate(args):
    """Train Autoencoder on benign data and IsolationForest on full data."""
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    # Load dataset (no SMOTE for unsupervised)
    data = load_dataset(
        cicids_dir=args.cicids_dir,
        unsw_dir=args.unsw_dir,
        apply_smote=False,
        n_folds=5,
        scale=True,
    )

    X = data["X"]
    y = data["y_binary"]

    # Split benign and attack
    benign_mask = y == 0
    attack_mask = y == 1
    X_benign = X[benign_mask]
    X_attack = X[attack_mask]

    log.info("Benign samples: %d, Attack samples: %d", len(X_benign), len(X_attack))

    # ---- Autoencoder ----
    log.info("=" * 50)
    log.info("Training Autoencoder on benign traffic...")
    ae = AutoencoderModel(epochs=args.ae_epochs, batch_size=256, learning_rate=1e-3)
    ae.train(X_benign)

    # Evaluate: score on full dataset
    ae_scores = ae.predict(X)
    ae_preds = (ae_scores > 0.5).astype(int)
    log.info(
        "Autoencoder  F1=%.4f  Prec=%.4f  Rec=%.4f",
        f1_score(y, ae_preds),
        precision_score(y, ae_preds, zero_division=0),
        recall_score(y, ae_preds),
    )

    ae.save(os.path.join(output_dir, "autoencoder_model.pt"))

    # ---- IsolationForest ----
    log.info("=" * 50)
    log.info("Training IsolationForest on full dataset...")
    iforest = IsolationForestModel(contamination=0.05)
    iforest.train(X)

    iforest_scores = iforest.predict(X)
    iforest_preds = (iforest_scores > 0.5).astype(int)
    log.info(
        "IsolationForest  F1=%.4f  Prec=%.4f  Rec=%.4f",
        f1_score(y, iforest_preds),
        precision_score(y, iforest_preds, zero_division=0),
        recall_score(y, iforest_preds),
    )

    iforest.save(os.path.join(output_dir, "isolation_forest_model.joblib"))

    # ---- Classification reports ----
    log.info("\n--- Autoencoder Classification Report ---")
    print(classification_report(y, ae_preds, target_names=["Benign", "Attack"], zero_division=0))

    log.info("\n--- IsolationForest Classification Report ---")
    print(classification_report(y, iforest_preds, target_names=["Benign", "Attack"], zero_division=0))

    # Save scaler
    if data["scaler"] is not None:
        import joblib
        scaler_path = os.path.join(output_dir, "scaler.joblib")
        if not os.path.exists(scaler_path):
            joblib.dump(data["scaler"], scaler_path)
            log.info("Scaler saved to %s", scaler_path)

    log.info("Unsupervised training complete. Models saved to %s", output_dir)


def main():
    parser = argparse.ArgumentParser(description="Train unsupervised ML models for ACDS")
    parser.add_argument("--cicids-dir", type=str, default=None, help="Path to CICIDS2017 CSV directory")
    parser.add_argument("--unsw-dir", type=str, default=None, help="Path to UNSW-NB15 CSV directory")
    parser.add_argument("--output-dir", type=str, default="./trained_models", help="Output directory")
    parser.add_argument("--ae-epochs", type=int, default=50, help="Autoencoder training epochs")
    args = parser.parse_args()

    if not args.cicids_dir and not args.unsw_dir:
        log.error("At least one dataset directory must be specified")
        sys.exit(1)

    train_and_evaluate(args)


if __name__ == "__main__":
    main()
