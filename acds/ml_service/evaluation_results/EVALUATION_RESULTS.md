# ACDS ML Model Evaluation Results

**Evaluated on:** 1,125,691 test samples (CICIDS2017 + UNSW-NB15)
**Dataset split:** 87.2% Benign | 12.8% Attack
**Generated:** 2026-03-20

---

## Overall Model Comparison

| Metric | XGBoost | RandomForest | Ensemble |
|---|---|---|---|
| **Accuracy** | 99.25% | 98.67% | 99.16% |
| **Precision** | 94.97% | 90.82% | 94.21% |
| **Recall** | 99.36% | 99.65% | 99.55% |
| **F1 Score** | 97.12% | 95.03% | 96.81% |
| **AUC-ROC** | 0.9996 | 0.9991 | 0.9995 |

---

## Per-Class Breakdown

### Benign (981,664 samples)

| Metric | XGBoost | RandomForest | Ensemble |
|---|---|---|---|
| Precision | 99.91% | 99.95% | 99.93% |
| Recall | 99.23% | 98.52% | 99.10% |
| F1 | 99.57% | 99.23% | 99.52% |

### Attack (144,027 samples)

| Metric | XGBoost | RandomForest | Ensemble |
|---|---|---|---|
| Precision | 94.97% | 90.82% | 94.21% |
| Recall | 99.36% | 99.65% | 99.55% |
| F1 | 97.12% | 95.03% | 96.81% |

---

## Key Takeaways

- **XGBoost is the best-performing model** — highest accuracy (99.25%), best F1 (97.12%), and best AUC (0.9996)
- **All models achieve near-perfect recall** (99.3%+) — they catch almost every attack
- **Precision is the tradeoff** — RandomForest has the most false positives (90.82% precision), meaning ~9% of flagged events are actually benign
- **AUC-ROC near 1.0 across the board** — excellent class separation across all models

---

## Generated Charts

| Chart | Description |
|---|---|
| `confusion_matrix_xgb.png` | XGBoost confusion matrix |
| `confusion_matrix_rf.png` | RandomForest confusion matrix |
| `confusion_matrix_ensemble.png` | Ensemble confusion matrix |
| `roc_curves.png` | ROC curves for all models |
| `precision_recall_curves.png` | Precision-Recall curves for all models |
| `feature_importance.png` | Top 14 feature importances (XGBoost vs RandomForest) |
| `score_distribution.png` | Ensemble score distribution (Benign vs Attack) |
| `detection_by_type.png` | Detection rate per attack category |
| `fpr_over_time.png` | False positive rate over time windows |
| `cv_scores.png` | 5-fold cross-validation F1 score box plots |
| `learning_curves_xgb.png` | XGBoost learning curves |
| `learning_curves_rf.png` | RandomForest learning curves |
| `model_comparison.png` | Side-by-side model comparison bar chart |
