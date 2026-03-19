"""
api.py — FastAPI endpoint for manual scoring and model management.

Endpoints:
    POST /score       - Score a feature vector with the ensemble
    GET  /models      - List all registered model versions
    GET  /models/active - Get the active model info
    GET  /health      - Health check
"""

import logging
import os
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ml_service.inference.onnx_runner import ONNXRunner
from ml_service.inference.threshold_manager import ThresholdManager
from ml_service.models.ensemble import EnsembleModel
from ml_service.registry.model_registry import ModelRegistry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ML-API] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ml_service.api")

# ---------------------------------------------------------------------------
# App and shared state
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ACDS ML Detection Service API",
    description="Manual scoring and model management for the ML detection pipeline.",
    version="1.0.0",
)

# Globals initialized on startup
_runner: Optional[ONNXRunner] = None
_ensemble: Optional[EnsembleModel] = None
_threshold_mgr: Optional[ThresholdManager] = None
_registry: Optional[ModelRegistry] = None


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ScoreRequest(BaseModel):
    features: Dict[str, float] = Field(
        ...,
        description="Feature dict with 14 keys matching the unified feature vector",
        examples=[{
            "connection_frequency": 5.0,
            "avg_packet_size": 512.0,
            "entropy": 3.2,
            "burst_rate": 0.8,
            "inter_arrival_time": 0.05,
            "tls_fingerprint_encoded": 0.0,
            "window_10s_count": 12.0,
            "window_30s_count": 30.0,
            "window_60s_count": 55.0,
            "window_avg_entropy": 3.1,
            "window_max_burst": 1.2,
            "window_unique_dst_ports": 3.0,
            "process_connection_count": 8.0,
            "container_unique_dst_ips": 2.0,
        }],
    )


class ScoreResponse(BaseModel):
    ensemble_score: float
    supervised_score: float
    unsupervised_score: float
    predicted_label: str
    risk_level: str
    threshold: float
    is_alert: bool


class ModelInfo(BaseModel):
    version: str
    model_paths: Dict[str, str]
    metrics: Dict[str, Any]
    description: str
    registered_at: float
    is_active: bool


# ---------------------------------------------------------------------------
# Feature ordering
# ---------------------------------------------------------------------------

FEATURE_ORDER = [
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


def _features_to_array(features: Dict[str, float]) -> np.ndarray:
    """Convert feature dict to a (1, 14) numpy array in canonical order."""
    vec = [features.get(name, 0.0) for name in FEATURE_ORDER]
    return np.array([vec], dtype=np.float32)


# ---------------------------------------------------------------------------
# Startup / Shutdown
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    global _runner, _ensemble, _threshold_mgr, _registry

    _registry = ModelRegistry()
    _ensemble = EnsembleModel()
    _threshold_mgr = ThresholdManager()
    _runner = ONNXRunner()

    # Attempt to load active model ONNX files
    active = _registry.get_active()
    if active:
        paths = active.get("model_paths", {})
        for name, path in paths.items():
            if os.path.exists(path) and path.endswith(".onnx"):
                try:
                    _runner.load_model(name, path)
                except Exception as e:
                    log.warning("Failed to load ONNX model '%s': %s", name, e)
        log.info("Active model version: %s", active["version"])
    else:
        log.info("No active model version in registry. Scoring will use fallback.")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "loaded_models": _runner.list_models() if _runner else [],
        "threshold": _threshold_mgr.get_stats() if _threshold_mgr else {},
    }


@app.post("/score", response_model=ScoreResponse)
async def score(request: ScoreRequest):
    """Score a feature vector using the ensemble of loaded ONNX models."""
    if _runner is None or _ensemble is None or _threshold_mgr is None:
        raise HTTPException(status_code=503, detail="ML service not initialized")

    X = _features_to_array(request.features)

    # Get individual model scores (fallback to 0.5 if model not loaded)
    xgb_score = float(_runner.predict("xgboost", X)[0]) if _runner.is_loaded("xgboost") else 0.5
    rf_score = float(_runner.predict("random_forest", X)[0]) if _runner.is_loaded("random_forest") else 0.5
    ae_score = float(_runner.predict_autoencoder_score("autoencoder", X)[0]) if _runner.is_loaded("autoencoder") else 0.5
    iforest_score = float(_runner.predict("isolation_forest", X)[0]) if _runner.is_loaded("isolation_forest") else 0.5

    result = _ensemble.predict(xgb_score, rf_score, ae_score, iforest_score)

    ens_score = result["ensemble_score"]
    _threshold_mgr.add_score(ens_score)

    return ScoreResponse(
        ensemble_score=ens_score,
        supervised_score=result["supervised_score"],
        unsupervised_score=result["unsupervised_score"],
        predicted_label=result["predicted_label"],
        risk_level=_threshold_mgr.get_risk_level(ens_score),
        threshold=_threshold_mgr.threshold,
        is_alert=_threshold_mgr.should_alert(ens_score),
    )


@app.get("/models", response_model=List[ModelInfo])
async def list_models():
    """List all registered model versions."""
    if _registry is None:
        raise HTTPException(status_code=503, detail="Registry not initialized")

    versions = _registry.list_versions()
    return [
        ModelInfo(
            version=v["version"],
            model_paths=v["model_paths"],
            metrics=v["metrics"],
            description=v.get("description", ""),
            registered_at=v["registered_at"],
            is_active=v.get("is_active", False),
        )
        for v in versions
    ]


@app.get("/models/active")
async def active_model():
    """Get the currently active model version."""
    if _registry is None:
        raise HTTPException(status_code=503, detail="Registry not initialized")

    active = _registry.get_active()
    if active is None:
        raise HTTPException(status_code=404, detail="No active model version set")

    return ModelInfo(
        version=active["version"],
        model_paths=active["model_paths"],
        metrics=active["metrics"],
        description=active.get("description", ""),
        registered_at=active["registered_at"],
        is_active=True,
    )


# ---------------------------------------------------------------------------
# Evaluation results directory
# ---------------------------------------------------------------------------

EVALUATION_DIR = os.path.join(os.path.dirname(__file__), "evaluation_results")


# ---------------------------------------------------------------------------
# Evaluation endpoints
# ---------------------------------------------------------------------------

@app.get("/evaluation/summary")
async def evaluation_summary():
    """Return the JSON metrics summary from the most recent evaluation run."""
    report_path = os.path.join(EVALUATION_DIR, "evaluation_report.json")
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="No evaluation report found. Run evaluate.py first.")

    import json
    with open(report_path, "r") as f:
        data = json.load(f)
    return data


@app.get("/evaluation/charts")
async def evaluation_charts():
    """Return a list of available chart filenames."""
    if not os.path.isdir(EVALUATION_DIR):
        raise HTTPException(status_code=404, detail="Evaluation results directory not found.")

    charts = [
        f for f in os.listdir(EVALUATION_DIR)
        if f.lower().endswith(".png")
    ]
    charts.sort()
    return {"charts": charts}


@app.get("/evaluation/chart/{filename}")
async def evaluation_chart(filename: str):
    """Serve a chart PNG by filename."""
    # Sanitize: only allow simple filenames (no path traversal)
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    filepath = os.path.join(EVALUATION_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"Chart '{filename}' not found.")

    return FileResponse(filepath, media_type="image/png", filename=filename)


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
