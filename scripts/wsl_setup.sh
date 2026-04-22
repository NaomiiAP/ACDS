#!/usr/bin/env bash
# =============================================================================
#  ACDS — WSL2 One-Shot Setup Script
#  Run inside WSL2:  bash /path/to/ACDS/scripts/wsl_setup.sh
# =============================================================================
set -e

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"

echo ""
echo "============================================================"
echo "  ACDS WSL2 Setup Script"
echo "  Project root: ${PROJECT_DIR}"
echo "============================================================"
echo ""

# ---------------------------------------------------------------------------
# 1. System packages
# ---------------------------------------------------------------------------
echo "[1/6] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3 python3-pip python3-venv \
    curl iputils-ping dnsutils git

echo ""

# ---------------------------------------------------------------------------
# 2. eBPF / BCC tooling  (apt, not pip)
# ---------------------------------------------------------------------------
echo "[2/6] Installing eBPF / BCC packages..."
sudo apt-get install -y -qq \
    bpfcc-tools python3-bpfcc linux-headers-$(uname -r) || {
    echo "  [WARN] Could not install linux-headers-$(uname -r) — eBPF agent may not compile."
    echo "         Try:  sudo apt install linux-headers-generic"
}
echo ""

# ---------------------------------------------------------------------------
# 3. Python: DPI Service venv
# ---------------------------------------------------------------------------
echo "[3/6] Setting up Python venvs..."

setup_venv() {
    local DIR="$1"
    local REQ="$2"
    echo "  → venv in ${DIR}"
    python3 -m venv "${DIR}/.venv"
    "${DIR}/.venv/bin/pip" install --quiet --upgrade pip
    "${DIR}/.venv/bin/pip" install --quiet -r "${REQ}"
    echo "    done."
}

setup_venv "${PROJECT_DIR}/dpi_service" \
           "${PROJECT_DIR}/dpi_service/requirements.txt"

setup_venv "${PROJECT_DIR}/acds/correlation_service" \
           "${PROJECT_DIR}/acds/correlation_service/requirements.txt"

setup_venv "${PROJECT_DIR}/acds/ui/backend" \
           "${PROJECT_DIR}/acds/ui/backend/requirements.txt"

# Telemetry agent: use --system-site-packages so BCC is visible
echo "  → venv in ${PROJECT_DIR}/acds/telemetry (with system-site-packages for BCC)"
python3 -m venv --system-site-packages "${PROJECT_DIR}/acds/telemetry/.venv"
"${PROJECT_DIR}/acds/telemetry/.venv/bin/pip" install --quiet --upgrade pip
"${PROJECT_DIR}/acds/telemetry/.venv/bin/pip" install --quiet \
    "confluent-kafka>=2.3.0" "jsonschema>=4.0.0"
echo "    done."

echo ""

# ---------------------------------------------------------------------------
# 4. Node.js via nvm (if not already installed)
# ---------------------------------------------------------------------------
echo "[4/6] Checking / installing Node.js..."
if ! command -v node &>/dev/null; then
    echo "  → Installing nvm..."
    curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    # shellcheck disable=SC1090
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
    nvm install --lts
    nvm use --lts
else
    echo "  Node.js $(node --version) already installed."
fi

NODE_VER=$(node --version 2>/dev/null || echo "unknown")
echo "  Node: ${NODE_VER}"

# ---------------------------------------------------------------------------
# 5. Frontend npm install
# ---------------------------------------------------------------------------
echo ""
echo "[5/6] Installing frontend npm packages..."
cd "${PROJECT_DIR}/acds/ui/frontend"

# Enable nvm in this shell if not already
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"

npm install --silent
echo "  npm install done."

# ---------------------------------------------------------------------------
# 6. Make scripts executable
# ---------------------------------------------------------------------------
echo ""
echo "[6/6] Making scripts executable..."
chmod +x "${PROJECT_DIR}/scripts/open_terminals.sh"
chmod +x "${PROJECT_DIR}/scripts/generate_traffic.sh"

# ---------------------------------------------------------------------------
# Done!
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  ✅  ACDS WSL2 setup complete!"
echo "============================================================"
echo ""
echo "  Docker Desktop must be running on Windows with WSL2 integration enabled."
echo ""
echo "  To start the full stack:"
echo "    cd ${PROJECT_DIR}"
echo "    ./scripts/open_terminals.sh"
echo ""
echo "  ─── Service URLs (once running) ─────────────────────────"
echo "    React Dashboard : http://localhost:5173"
echo "    FastAPI Docs    : http://localhost:8000/docs"
echo "    Kafka UI        : http://localhost:8080"
echo "============================================================"
