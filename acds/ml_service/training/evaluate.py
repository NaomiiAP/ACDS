"""
evaluate.py — Comprehensive model evaluation with metrics and chart generation.

Generates confusion matrices, ROC curves, PR curves, feature importance,
score distributions, detection-by-type charts, CV score box plots, and
model comparison bar charts.  All plots use a dark theme with the ACDS
dashboard color scheme (emerald green / red / amber).

Usage:
    python -m ml_service.training.evaluate \
        --models-dir ./trained_models \
        --cicids-dir /path/to/cicids2017 \
        --unsw-dir /path/to/unsw_nb15 \
        --output-dir ./evaluation_results
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    auc,
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_curve,
)
from sklearn.model_selection import cross_val_score, StratifiedKFold

from ml_service.models.supervised import (
    FEATURE_NAMES,
    RandomForestModel,
    XGBoostModel,
)
from ml_service.models.ensemble import ATTACK_LABELS, EnsembleModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [EVALUATE] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("evaluate")

# ---------------------------------------------------------------------------
# ACDS dark theme colors
# ---------------------------------------------------------------------------
EMERALD = "#10b981"
RED = "#ef4444"
AMBER = "#f59e0b"
CYAN = "#06b6d4"
BLUE = "#3b82f6"
PURPLE = "#8b5cf6"
SLATE = "#94a3b8"

MODEL_COLORS = {
    "XGBoost": BLUE,
    "RandomForest": PURPLE,
    "Ensemble": EMERALD,
}


def _apply_dark_style():
    """Apply dark background style with ACDS color palette."""
    plt.style.use("dark_background")
    plt.rcParams.update({
        "figure.facecolor": "#0a0d12",
        "axes.facecolor": "#111620",
        "axes.edgecolor": "rgba(255,255,255,0.15)",
        "axes.labelcolor": SLATE,
        "xtick.color": SLATE,
        "ytick.color": SLATE,
        "text.color": "#e2e8f0",
        "grid.color": "rgba(255,255,255,0.06)",
        "legend.facecolor": "#111620",
        "legend.edgecolor": "rgba(255,255,255,0.1)",
        "font.size": 11,
        "figure.dpi": 150,
    })


# ---------------------------------------------------------------------------
# Individual plot functions
# ---------------------------------------------------------------------------

def plot_confusion_matrix(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    labels: List[str],
    title: str,
    save_path: str,
) -> None:
    """Plot and save a confusion matrix heatmap."""
    _apply_dark_style()
    cm = confusion_matrix(y_true, y_pred)
    fig, ax = plt.subplots(figsize=(7, 6))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="RdYlGn_r",
        xticklabels=labels,
        yticklabels=labels,
        linewidths=0.5,
        linecolor="rgba(255,255,255,0.1)",
        cbar_kws={"shrink": 0.8},
        ax=ax,
    )
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Actual")
    ax.set_title(title, fontsize=14, fontweight="bold", color="#e2e8f0", pad=12)
    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    log.info("Saved %s", save_path)


def plot_roc_curves(
    models_dict: Dict[str, Tuple[np.ndarray, np.ndarray]],
    X_test: np.ndarray,
    y_test: np.ndarray,
    save_path: str,
) -> Dict[str, float]:
    """
    Plot ROC curves for all models on a single figure.

    Parameters
    ----------
    models_dict : {"ModelName": model_instance, ...}
        Each model must have a ``predict_proba`` method.
    X_test, y_test : test data
    save_path : output PNG path

    Returns
    -------
    dict of model_name -> AUC value
    """
    _apply_dark_style()
    fig, ax = plt.subplots(figsize=(8, 7))

    auc_values = {}
    for name, model in models_dict.items():
        scores = model.predict_proba(X_test)
        fpr, tpr, _ = roc_curve(y_test, scores)
        roc_auc = auc(fpr, tpr)
        auc_values[name] = round(float(roc_auc), 4)
        color = MODEL_COLORS.get(name, CYAN)
        ax.plot(fpr, tpr, color=color, lw=2, label=f"{name}  (AUC = {roc_auc:.4f})")

    ax.plot([0, 1], [0, 1], linestyle="--", color="rgba(255,255,255,0.2)", lw=1)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC Curves", fontsize=14, fontweight="bold", color="#e2e8f0", pad=12)
    ax.legend(loc="lower right", fontsize=10)
    ax.set_xlim([0, 1])
    ax.set_ylim([0, 1.02])
    ax.grid(True, alpha=0.15)
    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    log.info("Saved %s", save_path)
    return auc_values


def plot_precision_recall(
    models_dict: Dict[str, Any],
    X_test: np.ndarray,
    y_test: np.ndarray,
    save_path: str,
) -> None:
    """Plot Precision-Recall curves for all models on one figure."""
    _apply_dark_style()
    fig, ax = plt.subplots(figsize=(8, 7))

    for name, model in models_dict.items():
        scores = model.predict_proba(X_test)
        prec, rec, _ = precision_recall_curve(y_test, scores)
        pr_auc = auc(rec, prec)
        color = MODEL_COLORS.get(name, CYAN)
        ax.plot(rec, prec, color=color, lw=2, label=f"{name}  (AUC = {pr_auc:.4f})")

    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("Precision-Recall Curves", fontsize=14, fontweight="bold", color="#e2e8f0", pad=12)
    ax.legend(loc="lower left", fontsize=10)
    ax.set_xlim([0, 1])
    ax.set_ylim([0, 1.02])
    ax.grid(True, alpha=0.15)
    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    log.info("Saved %s", save_path)


def plot_feature_importance(
    xgb_model: XGBoostModel,
    rf_model: RandomForestModel,
    feature_names: List[str],
    save_path: str,
    top_n: int = 14,
) -> None:
    """Plot combined feature importance from XGBoost and RandomForest."""
    _apply_dark_style()

    xgb_imp = xgb_model.model.feature_importances_
    rf_imp = rf_model.model.feature_importances_

    # Average importance across both models
    combined = (xgb_imp + rf_imp) / 2.0
    indices = np.argsort(combined)[::-1][:top_n]

    names = [feature_names[i] for i in indices]
    xgb_vals = xgb_imp[indices]
    rf_vals = rf_imp[indices]

    fig, ax = plt.subplots(figsize=(10, 7))
    x = np.arange(len(names))
    width = 0.35

    ax.barh(x + width / 2, xgb_vals[::-1], width, label="XGBoost", color=BLUE, alpha=0.85)
    ax.barh(x - width / 2, rf_vals[::-1], width, label="RandomForest", color=PURPLE, alpha=0.85)

    ax.set_yticks(x)
    ax.set_yticklabels(names[::-1], fontsize=9)
    ax.set_xlabel("Feature Importance")
    ax.set_title(f"Top {top_n} Feature Importances", fontsize=14, fontweight="bold", color="#e2e8f0", pad=12)
    ax.legend(loc="lower right", fontsize=10)
    ax.grid(True, axis="x", alpha=0.15)
    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    log.info("Saved %s", save_path)


def plot_score_distribution(
    scores_benign: np.ndarray,
    scores_attack: np.ndarray,
    save_path: str,
) -> None:
    """Histogram of ensemble scores for benign vs attack samples."""
    _apply_dark_style()
    fig, ax = plt.subplots(figsize=(9, 6))

    ax.hist(scores_benign, bins=50, alpha=0.7, color=EMERALD, label="Benign", density=True)
    ax.hist(scores_attack, bins=50, alpha=0.7, color=RED, label="Attack", density=True)

    ax.axvline(x=0.5, linestyle="--", color=AMBER, lw=1.5, label="Threshold (0.5)")
    ax.set_xlabel("Ensemble Score")
    ax.set_ylabel("Density")
    ax.set_title("Score Distribution: Benign vs Attack", fontsize=14, fontweight="bold", color="#e2e8f0", pad=12)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.15)
    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    log.info("Saved %s", save_path)


def plot_detection_by_type(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    label_names: Dict[int, str],
    save_path: str,
) -> None:
    """Bar chart of detection rate (recall) per attack category."""
    _apply_dark_style()

    categories = {}
    for true_label, pred_label in zip(y_true, y_pred):
        name = label_names.get(int(true_label), f"Class {true_label}")
        if name == "Benign":
            continue
        if name not in categories:
            categories[name] = {"total": 0, "detected": 0}
        categories[name]["total"] += 1
        if pred_label >= 0.5 if isinstance(pred_label, float) else pred_label > 0:
            categories[name]["detected"] += 1

    if not categories:
        log.warning("No attack categories found for detection_by_type chart.")
        return

    names = sorted(categories.keys())
    rates = [categories[n]["detected"] / max(categories[n]["total"], 1) for n in names]

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = [EMERALD if r >= 0.9 else AMBER if r >= 0.7 else RED for r in rates]
    bars = ax.bar(names, rates, color=colors, alpha=0.85, edgecolor="rgba(255,255,255,0.1)")

    for bar, rate in zip(bars, rates):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.02,
            f"{rate:.1%}",
            ha="center",
            va="bottom",
            fontsize=9,
            color="#e2e8f0",
        )

    ax.set_ylabel("Detection Rate")
    ax.set_title("Detection Rate by Attack Type", fontsize=14, fontweight="bold", color="#e2e8f0", pad=12)
    ax.set_ylim([0, 1.15])
    ax.grid(True, axis="y", alpha=0.15)
    plt.xticks(rotation=30, ha="right")
    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    log.info("Saved %s", save_path)


def plot_cv_scores(
    cv_scores_dict: Dict[str, np.ndarray],
    save_path: str,
) -> None:
    """Box plot of cross-validation F1 scores for each model."""
    _apply_dark_style()
    fig, ax = plt.subplots(figsize=(8, 6))

    data = []
    labels = []
    colors = []
    for name, scores in cv_scores_dict.items():
        data.append(scores)
        labels.append(name)
        colors.append(MODEL_COLORS.get(name, CYAN))

    bp = ax.boxplot(
        data,
        labels=labels,
        patch_artist=True,
        widths=0.5,
        medianprops={"color": "#e2e8f0", "linewidth": 2},
        whiskerprops={"color": SLATE},
        capprops={"color": SLATE},
        flierprops={"markerfacecolor": RED, "markersize": 5},
    )
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
        patch.set_edgecolor("rgba(255,255,255,0.3)")

    ax.set_ylabel("F1 Score")
    ax.set_title("Cross-Validation F1 Scores", fontsize=14, fontweight="bold", color="#e2e8f0", pad=12)
    ax.grid(True, axis="y", alpha=0.15)
    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    log.info("Saved %s", save_path)


def plot_model_comparison(
    metrics_dict: Dict[str, Dict[str, float]],
    save_path: str,
) -> None:
    """Grouped bar chart comparing all models on accuracy, precision, recall, F1."""
    _apply_dark_style()
    fig, ax = plt.subplots(figsize=(10, 6))

    metric_names = ["accuracy", "precision", "recall", "f1"]
    model_names = list(metrics_dict.keys())
    n_metrics = len(metric_names)
    n_models = len(model_names)
    x = np.arange(n_metrics)
    width = 0.8 / n_models

    for i, name in enumerate(model_names):
        vals = [metrics_dict[name].get(m, 0.0) for m in metric_names]
        color = MODEL_COLORS.get(name, CYAN)
        bars = ax.bar(x + i * width - (n_models - 1) * width / 2, vals, width,
                      label=name, color=color, alpha=0.85, edgecolor="rgba(255,255,255,0.1)")
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                    f"{v:.3f}", ha="center", va="bottom", fontsize=8, color="#e2e8f0")

    ax.set_xticks(x)
    ax.set_xticklabels([m.capitalize() for m in metric_names])
    ax.set_ylabel("Score")
    ax.set_ylim([0, 1.12])
    ax.set_title("Model Comparison", fontsize=14, fontweight="bold", color="#e2e8f0", pad=12)
    ax.legend(fontsize=10)
    ax.grid(True, axis="y", alpha=0.15)
    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    log.info("Saved %s", save_path)


def plot_fpr_over_time(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    window_size: int,
    save_path: str,
) -> None:
    """False positive rate computed in sliding windows."""
    _apply_dark_style()

    n = len(y_true)
    if n < window_size:
        log.warning("Not enough samples (%d) for FPR time-window chart (window=%d)", n, window_size)
        return

    fprs = []
    window_centers = []
    for start in range(0, n - window_size + 1, window_size // 2):
        end = start + window_size
        yt = y_true[start:end]
        yp = y_pred[start:end]
        negatives = (yt == 0)
        if negatives.sum() == 0:
            continue
        fp = ((yp == 1) & (yt == 0)).sum()
        fpr_val = fp / negatives.sum()
        fprs.append(fpr_val)
        window_centers.append((start + end) / 2)

    if not fprs:
        return

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(window_centers, fprs, color=RED, lw=2, marker="o", markersize=4)
    ax.fill_between(window_centers, fprs, alpha=0.15, color=RED)
    ax.set_xlabel("Sample Index (window center)")
    ax.set_ylabel("False Positive Rate")
    ax.set_title("False Positive Rate Over Time Windows", fontsize=14, fontweight="bold", color="#e2e8f0", pad=12)
    ax.grid(True, alpha=0.15)
    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    log.info("Saved %s", save_path)


def plot_learning_curves(
    model,
    X: np.ndarray,
    y: np.ndarray,
    model_name: str,
    save_path: str,
    cv: int = 5,
    n_points: int = 8,
) -> None:
    """Plot learning curves (train & validation score vs training size)."""
    _apply_dark_style()
    from sklearn.model_selection import learning_curve

    train_sizes, train_scores, val_scores = learning_curve(
        model,
        X,
        y,
        cv=cv,
        scoring="f1",
        train_sizes=np.linspace(0.1, 1.0, n_points),
        n_jobs=-1,
    )

    train_mean = train_scores.mean(axis=1)
    train_std = train_scores.std(axis=1)
    val_mean = val_scores.mean(axis=1)
    val_std = val_scores.std(axis=1)

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.fill_between(train_sizes, train_mean - train_std, train_mean + train_std, alpha=0.15, color=BLUE)
    ax.fill_between(train_sizes, val_mean - val_std, val_mean + val_std, alpha=0.15, color=EMERALD)
    ax.plot(train_sizes, train_mean, "o-", color=BLUE, lw=2, label="Training F1")
    ax.plot(train_sizes, val_mean, "o-", color=EMERALD, lw=2, label="Validation F1")

    ax.set_xlabel("Training Set Size")
    ax.set_ylabel("F1 Score")
    ax.set_title(f"Learning Curves — {model_name}", fontsize=14, fontweight="bold", color="#e2e8f0", pad=12)
    ax.legend(loc="lower right", fontsize=10)
    ax.grid(True, alpha=0.15)
    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    log.info("Saved %s", save_path)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(metrics: Dict[str, Any], output_dir: str) -> str:
    """Save evaluation metrics as JSON and a human-readable text summary."""
    os.makedirs(output_dir, exist_ok=True)

    # JSON report
    json_path = os.path.join(output_dir, "evaluation_report.json")
    with open(json_path, "w") as f:
        json.dump(metrics, f, indent=2, default=str)
    log.info("Saved JSON report to %s", json_path)

    # Text summary
    txt_path = os.path.join(output_dir, "evaluation_report.txt")
    lines = [
        "=" * 60,
        "ACDS MODEL EVALUATION REPORT",
        f"Generated: {datetime.now().isoformat()}",
        "=" * 60,
        "",
    ]

    for model_name, model_metrics in metrics.get("models", {}).items():
        lines.append(f"--- {model_name} ---")
        for k, v in model_metrics.items():
            if isinstance(v, float):
                lines.append(f"  {k:20s}: {v:.4f}")
            else:
                lines.append(f"  {k:20s}: {v}")
        lines.append("")

    if "auc_values" in metrics:
        lines.append("--- AUC Values ---")
        for name, val in metrics["auc_values"].items():
            lines.append(f"  {name:20s}: {val:.4f}")
        lines.append("")

    if "charts" in metrics:
        lines.append("--- Generated Charts ---")
        for chart in metrics["charts"]:
            lines.append(f"  - {chart}")
        lines.append("")

    lines.append("=" * 60)
    text = "\n".join(lines)

    with open(txt_path, "w") as f:
        f.write(text)
    log.info("Saved text report to %s", txt_path)

    return json_path


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

class _EnsembleWrapper:
    """Thin wrapper so the ensemble can be used like the other models in ROC/PR plots."""

    def __init__(self, xgb_model: XGBoostModel, rf_model: RandomForestModel):
        self.xgb = xgb_model
        self.rf = rf_model
        self.ensemble = EnsembleModel()

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        xgb_scores = self.xgb.predict_proba(X)
        rf_scores = self.rf.predict_proba(X)
        # Use only supervised scores for ensemble wrapper (ae/iforest default 0.5)
        dummy = np.full_like(xgb_scores, 0.5)
        return self.ensemble.predict_batch(xgb_scores, rf_scores, dummy, dummy)

    def predict(self, X: np.ndarray) -> np.ndarray:
        scores = self.predict_proba(X)
        return (scores >= 0.5).astype(int)


def evaluate_all(
    models_dict: Dict[str, Any],
    X_test: np.ndarray,
    y_test: np.ndarray,
    feature_names: List[str],
    output_dir: str,
    X_full: Optional[np.ndarray] = None,
    y_full: Optional[np.ndarray] = None,
    y_test_multiclass: Optional[np.ndarray] = None,
    attack_labels: Optional[Dict[int, str]] = None,
) -> Dict[str, Any]:
    """
    Run all evaluations and generate charts.

    Parameters
    ----------
    models_dict : {"xgboost": XGBoostModel, "random_forest": RandomForestModel}
    X_test, y_test : test split (binary labels: 0 = benign, 1 = attack)
    feature_names : list of feature column names
    output_dir : directory to save charts and reports
    X_full, y_full : full dataset (optional, for learning curves / CV)
    y_test_multiclass : multi-class labels for detection-by-type (optional)
    attack_labels : {int: str} mapping for multi-class labels (optional)
    """
    os.makedirs(output_dir, exist_ok=True)
    attack_labels = attack_labels or ATTACK_LABELS
    labels = ["Benign", "Attack"]

    xgb_model: XGBoostModel = models_dict["xgboost"]
    rf_model: RandomForestModel = models_dict["random_forest"]
    ensemble_wrapper = _EnsembleWrapper(xgb_model, rf_model)

    # Predictions
    xgb_pred = xgb_model.predict(X_test)
    rf_pred = rf_model.predict(X_test)
    ens_pred = ensemble_wrapper.predict(X_test)

    charts = []

    # ---- Confusion matrices ----
    for name, preds, fname in [
        ("XGBoost", xgb_pred, "confusion_matrix_xgb.png"),
        ("RandomForest", rf_pred, "confusion_matrix_rf.png"),
        ("Ensemble", ens_pred, "confusion_matrix_ensemble.png"),
    ]:
        path = os.path.join(output_dir, fname)
        plot_confusion_matrix(y_test, preds, labels, f"Confusion Matrix — {name}", path)
        charts.append(fname)

    # ---- ROC curves ----
    roc_models = {
        "XGBoost": xgb_model,
        "RandomForest": rf_model,
        "Ensemble": ensemble_wrapper,
    }
    roc_path = os.path.join(output_dir, "roc_curves.png")
    auc_values = plot_roc_curves(roc_models, X_test, y_test, roc_path)
    charts.append("roc_curves.png")

    # ---- Precision-Recall curves ----
    pr_path = os.path.join(output_dir, "precision_recall_curves.png")
    plot_precision_recall(roc_models, X_test, y_test, pr_path)
    charts.append("precision_recall_curves.png")

    # ---- Feature importance ----
    fi_path = os.path.join(output_dir, "feature_importance.png")
    plot_feature_importance(xgb_model, rf_model, feature_names, fi_path)
    charts.append("feature_importance.png")

    # ---- Score distribution ----
    ens_scores = ensemble_wrapper.predict_proba(X_test)
    benign_mask = y_test == 0
    attack_mask = y_test == 1
    sd_path = os.path.join(output_dir, "score_distribution.png")
    plot_score_distribution(ens_scores[benign_mask], ens_scores[attack_mask], sd_path)
    charts.append("score_distribution.png")

    # ---- Detection by type (if multi-class labels available) ----
    if y_test_multiclass is not None:
        dt_path = os.path.join(output_dir, "detection_by_type.png")
        plot_detection_by_type(y_test_multiclass, ens_pred, attack_labels, dt_path)
        charts.append("detection_by_type.png")

    # ---- FPR over time windows ----
    fpr_path = os.path.join(output_dir, "fpr_over_time.png")
    window_size = max(100, len(y_test) // 20)
    plot_fpr_over_time(y_test, ens_pred, window_size, fpr_path)
    charts.append("fpr_over_time.png")

    # ---- Cross-validation scores (if full dataset provided) ----
    if X_full is not None and y_full is not None:
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

        xgb_cv = cross_val_score(xgb_model.model, X_full, y_full, cv=skf, scoring="f1", n_jobs=-1)
        rf_cv = cross_val_score(rf_model.model, X_full, y_full, cv=skf, scoring="f1", n_jobs=-1)

        cv_path = os.path.join(output_dir, "cv_scores.png")
        plot_cv_scores({"XGBoost": xgb_cv, "RandomForest": rf_cv}, cv_path)
        charts.append("cv_scores.png")

        # ---- Learning curves ----
        lc_xgb_path = os.path.join(output_dir, "learning_curves_xgb.png")
        plot_learning_curves(xgb_model.model, X_full, y_full, "XGBoost", lc_xgb_path)
        charts.append("learning_curves_xgb.png")

        lc_rf_path = os.path.join(output_dir, "learning_curves_rf.png")
        plot_learning_curves(rf_model.model, X_full, y_full, "RandomForest", lc_rf_path)
        charts.append("learning_curves_rf.png")

    # ---- Per-model metrics ----
    model_metrics = {}
    for name, preds in [("XGBoost", xgb_pred), ("RandomForest", rf_pred), ("Ensemble", ens_pred)]:
        model_metrics[name] = {
            "accuracy": round(float(accuracy_score(y_test, preds)), 4),
            "precision": round(float(precision_score(y_test, preds, zero_division=0)), 4),
            "recall": round(float(recall_score(y_test, preds, zero_division=0)), 4),
            "f1": round(float(f1_score(y_test, preds, zero_division=0)), 4),
            "auc": auc_values.get(name, 0.0),
        }

    # ---- Model comparison chart ----
    mc_path = os.path.join(output_dir, "model_comparison.png")
    plot_model_comparison(model_metrics, mc_path)
    charts.append("model_comparison.png")

    # ---- Classification reports ----
    classification_reports = {}
    for name, preds in [("XGBoost", xgb_pred), ("RandomForest", rf_pred), ("Ensemble", ens_pred)]:
        report = classification_report(y_test, preds, target_names=labels, output_dict=True)
        classification_reports[name] = report

    # ---- Build full metrics dict ----
    all_metrics = {
        "generated_at": datetime.now().isoformat(),
        "test_samples": int(len(y_test)),
        "models": model_metrics,
        "auc_values": auc_values,
        "classification_reports": classification_reports,
        "charts": charts,
    }

    # ---- Generate report ----
    generate_report(all_metrics, output_dir)

    log.info("Evaluation complete. %d charts generated in %s", len(charts), output_dir)
    return all_metrics


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Evaluate trained ACDS ML models")
    parser.add_argument("--models-dir", type=str, default="./trained_models")
    parser.add_argument("--cicids-dir", type=str, default=None)
    parser.add_argument("--unsw-dir", type=str, default=None)
    parser.add_argument("--output-dir", type=str, default="./evaluation_results")
    args = parser.parse_args()

    from ml_service.training.dataset_loader import load_dataset

    # Load models
    xgb = XGBoostModel()
    xgb.load(os.path.join(args.models_dir, "xgboost_model.joblib"))

    rf = RandomForestModel()
    rf.load(os.path.join(args.models_dir, "random_forest_model.joblib"))

    # Load dataset
    data = load_dataset(
        cicids_dir=args.cicids_dir,
        unsw_dir=args.unsw_dir,
        apply_smote=False,
        n_folds=5,
        scale=True,
    )

    X = data["X"]
    y = data["y_binary"]

    # Use last fold as test set
    folds = data["folds"]
    _, test_idx = folds[-1]
    X_test = X[test_idx]
    y_test = y[test_idx]

    y_multiclass = data.get("y_multiclass")
    y_test_mc = y_multiclass[test_idx] if y_multiclass is not None else None

    metrics = evaluate_all(
        models_dict={"xgboost": xgb, "random_forest": rf},
        X_test=X_test,
        y_test=y_test,
        feature_names=FEATURE_NAMES,
        output_dir=args.output_dir,
        X_full=X,
        y_full=y,
        y_test_multiclass=y_test_mc,
    )

    print(json.dumps(metrics["models"], indent=2))


if __name__ == "__main__":
    main()
