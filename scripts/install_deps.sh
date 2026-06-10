#!/usr/bin/env bash
# Install all Python dependencies into a shared project venv.
# Run from WSL: bash scripts/install_deps.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
VENV="${PROJECT_DIR}/.venv"

echo "============================================="
echo "  ACDS: Installing Python dependencies"
echo "============================================="

# DPI/Scapy needs system libpcap (not installable via pip)
if ! ldconfig -p 2>/dev/null | grep -q libpcap.so; then
    echo ""
    echo "WARNING: libpcap not found. DPI Service will fail until you run:"
    echo "  sudo apt-get update && sudo apt-get install -y libpcap-dev"
    echo ""
fi

if [ ! -d "${VENV}" ]; then
    echo "Creating virtualenv at ${VENV}"
    # --system-site-packages: telemetry agent needs system bcc (python3-bpfcc)
    python3 -m venv --system-site-packages "${VENV}"
fi

# shellcheck disable=SC1091
source "${VENV}/bin/activate"

pip install --upgrade pip

echo "[1/7] Backend API..."
pip install -r "${PROJECT_DIR}/acds/ui/backend/requirements.txt"

echo "[2/7] Correlation Service..."
pip install -r "${PROJECT_DIR}/acds/correlation_service/requirements.txt"

echo "[3/7] DPI Service..."
pip install -r "${PROJECT_DIR}/dpi_service/requirements.txt"

echo "[4/7] Graph Service..."
pip install -r "${PROJECT_DIR}/acds/graph_service/requirements.txt"

echo "[5/7] LLM Service..."
pip install -r "${PROJECT_DIR}/acds/llm_service/requirements.txt"

echo "[6/7] Telemetry agent - Kafka + schema, bcc from apt..."
pip install "confluent-kafka>=2.3.0" "jsonschema>=4.0.0"
# System Python runs the eBPF agent; install Kafka deps for /usr/bin/python3 too
pip3 install --user "confluent-kafka>=2.3.0" "jsonschema>=4.0.0" 2>/dev/null || true

echo "[7/7] ML Service - may take a few minutes..."
pip install -r "${PROJECT_DIR}/acds/ml_service/requirements.txt"

pip install python-dotenv

echo ""
echo "Done. All services use: ${VENV}/bin/python3"
echo "Activate manually: source .venv/bin/activate"
