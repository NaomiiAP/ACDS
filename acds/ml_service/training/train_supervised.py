"""
train_supervised.py — Train XGBoost and RandomForest on CICIDS2017/UNSW-NB15.

Usage:
    python -m ml_service.training.train_supervised \
        --cicids-dir /path/to/cicids2017 \
        --unsw-dir /path/to/unsw_nb15 \
        --output-dir ./trained_models
"""

import argparse
import logging
import os
import sys
import time

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)

from ml_service.training.dataset_loader import load_dataset
from ml_service.models.supervised import XGBoostModel, RandomForestModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [TRAIN-SUP] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("train_supervised")


def train_and_evaluate(args):
    """Load data, train models with cross-validation, save best models."""
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    # Load dataset
    data = load_dataset(
        cicids_dir=args.cicids_dir,
        unsw_dir=args.unsw_dir,
        apply_smote=True,
        n_folds=5,
        scale=True,
    )

    X = data["X"]
    y = data["y_binary"]
    folds = data["folds"]

    log.info("Dataset loaded: %d samples, %d features", X.shape[0], X.shape[1])

    # ---- Cross-validation ----
    xgb_metrics = {"f1": [], "precision": [], "recall": [], "accuracy": []}
    rf_metrics = {"f1": [], "precision": [], "recall": [], "accuracy": []}

    for fold_idx, (train_idx, test_idx) in enumerate(folds):
        log.info("=" * 50)
        log.info("Fold %d/%d", fold_idx + 1, len(folds))
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        # XGBoost
        xgb = XGBoostModel()
        xgb.train(X_train, y_train)
        xgb_pred = xgb.predict(X_test)
        xgb_metrics["f1"].append(f1_score(y_test, xgb_pred))
        xgb_metrics["precision"].append(precision_score(y_test, xgb_pred))
        xgb_metrics["recall"].append(recall_score(y_test, xgb_pred))
        xgb_metrics["accuracy"].append(accuracy_score(y_test, xgb_pred))

        # RandomForest
        rf = RandomForestModel()
        rf.train(X_train, y_train)
        rf_pred = rf.predict(X_test)
        rf_metrics["f1"].append(f1_score(y_test, rf_pred))
        rf_metrics["precision"].append(precision_score(y_test, rf_pred))
        rf_metrics["recall"].append(recall_score(y_test, rf_pred))
        rf_metrics["accuracy"].append(accuracy_score(y_test, rf_pred))

        log.info(
            "  XGB  F1=%.4f  Prec=%.4f  Rec=%.4f  Acc=%.4f",
            xgb_metrics["f1"][-1],
            xgb_metrics["precision"][-1],
            xgb_metrics["recall"][-1],
            xgb_metrics["accuracy"][-1],
        )
        log.info(
            "  RF   F1=%.4f  Prec=%.4f  Rec=%.4f  Acc=%.4f",
            rf_metrics["f1"][-1],
            rf_metrics["precision"][-1],
            rf_metrics["recall"][-1],
            rf_metrics["accuracy"][-1],
        )

    # ---- Summary ----
    log.info("=" * 50)
    log.info("CROSS-VALIDATION SUMMARY (5-fold)")
    log.info("-" * 50)
    for name, metrics in [("XGBoost", xgb_metrics), ("RandomForest", rf_metrics)]:
        log.info(
            "%s  F1=%.4f +/- %.4f  Prec=%.4f  Rec=%.4f  Acc=%.4f",
            name,
            np.mean(metrics["f1"]),
            np.std(metrics["f1"]),
            np.mean(metrics["precision"]),
            np.mean(metrics["recall"]),
            np.mean(metrics["accuracy"]),
        )

    # ---- Train final models on full dataset ----
    log.info("Training final models on full dataset...")
    xgb_final = XGBoostModel()
    xgb_final.train(X, y)
    xgb_final.save(os.path.join(output_dir, "xgboost_model.joblib"))

    rf_final = RandomForestModel()
    rf_final.train(X, y)
    rf_final.save(os.path.join(output_dir, "random_forest_model.joblib"))

    # Print classification report on last fold's test set
    log.info("\n--- XGBoost Classification Report (last fold) ---")
    print(classification_report(y_test, xgb_pred, target_names=["Benign", "Attack"]))

    log.info("\n--- RandomForest Classification Report (last fold) ---")
    print(classification_report(y_test, rf_pred, target_names=["Benign", "Attack"]))

    # Save scaler
    if data["scaler"] is not None:
        import joblib
        joblib.dump(data["scaler"], os.path.join(output_dir, "scaler.joblib"))
        log.info("Scaler saved to %s", os.path.join(output_dir, "scaler.joblib"))

    log.info("Training complete. Models saved to %s", output_dir)


def main():
    parser = argparse.ArgumentParser(description="Train supervised ML models for ACDS")
    parser.add_argument("--cicids-dir", type=str, default=None, help="Path to CICIDS2017 CSV directory")
    parser.add_argument("--unsw-dir", type=str, default=None, help="Path to UNSW-NB15 CSV directory")
    parser.add_argument("--output-dir", type=str, default="./trained_models", help="Output directory for models")
    args = parser.parse_args()

    if not args.cicids_dir and not args.unsw_dir:
        log.error("At least one dataset directory must be specified (--cicids-dir or --unsw-dir)")
        sys.exit(1)

    train_and_evaluate(args)


if __name__ == "__main__":
    main()
