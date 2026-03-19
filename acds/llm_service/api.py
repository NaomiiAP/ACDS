"""
api.py — FastAPI endpoints for the LLM Triage Service.

Run standalone:  uvicorn api:app --host 0.0.0.0 --port 8900
"""

import time
import uuid
import logging

from fastapi import FastAPI, HTTPException

from ollama_client import OllamaClient
from prompt_templates import build_prompt
from triage_formatter import parse_llm_output

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [LLM-API] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("llm_triage.api")

app = FastAPI(
    title="ACDS LLM Triage Service",
    description="On-demand LLM-powered cybersecurity alert triage",
    version="1.0.0",
)

_ollama = OllamaClient()


@app.on_event("shutdown")
async def _shutdown():
    await _ollama.close()


@app.post("/triage")
async def triage_alert(alert: dict):
    """Accept an alert dict, run LLM triage, and return the structured result."""
    start_ms = time.time()

    prompt = build_prompt(alert)

    try:
        raw_output = await _ollama.generate(prompt)
    except Exception as exc:
        log.error("Ollama generation failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"LLM generation failed: {exc}")

    processing_time_ms = int((time.time() - start_ms) * 1000)
    parsed = parse_llm_output(raw_output)

    alert_id = alert.get("alert_id", str(uuid.uuid4()))

    return {
        "triage_id": str(uuid.uuid4()),
        "alert_id": alert_id,
        "timestamp": time.time(),
        "explanation": parsed["explanation"],
        "attack_stage": parsed["attack_stage"],
        "confidence": parsed["confidence"],
        "severity": parsed["severity"],
        "mitigation_steps": parsed["mitigation_steps"],
        "model_used": _ollama.model,
        "advisory_only": True,
        "processing_time_ms": processing_time_ms,
        "raw_llm_output": raw_output,
        "alert_context": {
            "ensemble_score": alert.get("ensemble_score"),
            "predicted_label": alert.get("predicted_label"),
            "risk_level": alert.get("risk_level"),
            "src_ip": alert.get("src_ip"),
            "dst_ip": alert.get("dst_ip"),
            "dst_port": alert.get("dst_port"),
            "process_name": alert.get("process_name"),
        },
    }


@app.get("/health")
async def health_check():
    """Check Ollama connectivity."""
    available = await _ollama.is_available()
    if available:
        return {"status": "healthy", "ollama": "reachable", "model": _ollama.model}
    return {"status": "degraded", "ollama": "unreachable", "model": _ollama.model}


@app.get("/models")
async def list_models():
    """List available Ollama models."""
    models = await _ollama.list_models()
    return {"models": models}
