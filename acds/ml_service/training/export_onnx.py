"""
export_onnx.py — Export trained models to ONNX format for fast inference.

Supports:
  - XGBoost       via onnxmltools
  - RandomForest  via skl2onnx
  - Autoencoder   via torch.onnx.export
  - IsolationForest via skl2onnx

Usage:
    python -m ml_service.training.export_onnx \
        --model-dir ./trained_models \
        --output-dir ./onnx_models
"""

import argparse
import logging
import os
import sys

import joblib
import numpy as np
import torch

log = logging.getLogger("ml_service.training.export_onnx")

NUM_FEATURES = 14


def export_xgboost(model_path: str, output_path: str) -> None:
    """Export a joblib-saved XGBClassifier to ONNX."""
    from onnxmltools import convert_xgboost
    from onnxmltools.convert.common.data_types import FloatTensorType

    log.info("Exporting XGBoost from %s", model_path)
    model = joblib.load(model_path)

    initial_type = [("features", FloatTensorType([None, NUM_FEATURES]))]
    onnx_model = convert_xgboost(model, initial_types=initial_type)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(onnx_model.SerializeToString())
    log.info("XGBoost ONNX model saved to %s", output_path)


def export_random_forest(model_path: str, output_path: str) -> None:
    """Export a joblib-saved RandomForestClassifier to ONNX."""
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType

    log.info("Exporting RandomForest from %s", model_path)
    model = joblib.load(model_path)

    initial_type = [("features", FloatTensorType([None, NUM_FEATURES]))]
    onnx_model = convert_sklearn(model, initial_types=initial_type)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(onnx_model.SerializeToString())
    log.info("RandomForest ONNX model saved to %s", output_path)


def export_autoencoder(model_path: str, output_path: str) -> None:
    """Export a PyTorch Autoencoder to ONNX."""
    from ml_service.models.unsupervised import AutoencoderModel

    log.info("Exporting Autoencoder from %s", model_path)
    ae = AutoencoderModel()
    ae.load(model_path)
    net = ae.get_pytorch_model()
    net.eval()

    dummy_input = torch.randn(1, NUM_FEATURES)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    # Use dynamo=False to avoid encoding issues on Windows
    torch.onnx.export(
        net,
        dummy_input,
        output_path,
        export_params=True,
        opset_version=18,
        input_names=["features"],
        output_names=["reconstruction"],
        dynamic_axes={
            "features": {0: "batch_size"},
            "reconstruction": {0: "batch_size"},
        },
        dynamo=False,
    )
    log.info("Autoencoder ONNX model saved to %s", output_path)


def export_isolation_forest(model_path: str, output_path: str) -> None:
    """Export a joblib-saved IsolationForest to ONNX."""
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType

    log.info("Exporting IsolationForest from %s", model_path)
    model = joblib.load(model_path)

    initial_type = [("features", FloatTensorType([None, NUM_FEATURES]))]
    onnx_model = convert_sklearn(
        model, initial_types=initial_type,
        target_opset={"": 17, "ai.onnx.ml": 3},
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(onnx_model.SerializeToString())
    log.info("IsolationForest ONNX model saved to %s", output_path)


def export_all(model_dir: str, output_dir: str) -> None:
    """Export all four models from model_dir to output_dir."""
    os.makedirs(output_dir, exist_ok=True)

    mappings = [
        ("xgboost_model.joblib", "xgboost.onnx", export_xgboost),
        ("random_forest_model.joblib", "random_forest.onnx", export_random_forest),
        ("autoencoder_model.pt", "autoencoder.onnx", export_autoencoder),
        ("isolation_forest_model.joblib", "isolation_forest.onnx", export_isolation_forest),
    ]

    for src_name, dst_name, export_fn in mappings:
        src = os.path.join(model_dir, src_name)
        dst = os.path.join(output_dir, dst_name)
        if os.path.exists(src):
            try:
                export_fn(src, dst)
            except Exception as e:
                log.error("Failed to export %s: %s", src_name, e)
        else:
            log.warning("Model file not found, skipping: %s", src)

    log.info("ONNX export complete. Output directory: %s", output_dir)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [EXPORT] %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(description="Export trained models to ONNX")
    parser.add_argument("--model-dir", type=str, default="./trained_models", help="Directory with trained models")
    parser.add_argument("--output-dir", type=str, default="./onnx_models", help="Output directory for ONNX models")
    args = parser.parse_args()

    export_all(args.model_dir, args.output_dir)


if __name__ == "__main__":
    main()
