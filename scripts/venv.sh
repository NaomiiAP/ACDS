#!/usr/bin/env bash
# Shared virtualenv setup for all ACDS launch scripts.
# Usage: source /path/to/ACDS/scripts/venv.sh

_VENV_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACDS_PROJECT_DIR="$(dirname "${_VENV_SCRIPT_DIR}")"
ACDS_VENV="${ACDS_PROJECT_DIR}/.venv"
ACDS_VENV_PY="${ACDS_VENV}/bin/python3"
# Telemetry needs system Python for bcc (eBPF); pip packages come from the venv
ACDS_TELEMETRY_PY="/usr/bin/python3"
ACDS_VENV_SITE="$("${ACDS_VENV_PY:-/usr/bin/python3}" -c "import site; print(site.getsitepackages()[0])" 2>/dev/null || echo "${ACDS_VENV}/lib/python3.12/site-packages")"
export PYTHONPATH="${ACDS_PROJECT_DIR}"

acds_ensure_venv() {
    if [ ! -x "${ACDS_VENV_PY}" ]; then
        echo "ACDS: creating virtualenv and installing dependencies..."
        bash "${ACDS_PROJECT_DIR}/scripts/install_deps.sh"
    fi
    if [ ! -x "${ACDS_VENV_PY}" ]; then
        echo "ERROR: virtualenv not found at ${ACDS_VENV_PY}"
        echo "Run: bash scripts/install_deps.sh"
        exit 1
    fi
}

acds_ensure_venv

# PYTHONPATH for telemetry agent: system bcc + venv Kafka packages
acds_telemetry_pythonpath() {
    echo "${ACDS_VENV_SITE}:${ACDS_PROJECT_DIR}/acds/telemetry/agent"
}
