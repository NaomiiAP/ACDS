#!/usr/bin/env bash
# Install/check system packages required by Telemetry (bcc) and DPI (libpcap).
# Run in WSL: bash scripts/ensure_system_deps.sh

set -e

MISSING=()

python3 -c "import bcc" 2>/dev/null || MISSING+=(bpfcc-tools python3-bpfcc)
ldconfig -p 2>/dev/null | grep -q libpcap.so || MISSING+=(libpcap-dev)

if [ ${#MISSING[@]} -eq 0 ]; then
    echo "System dependencies OK (bcc, libpcap)"
    exit 0
fi

echo "Installing missing system packages: ${MISSING[*]}"
sudo apt-get update -qq
sudo apt-get install -y -qq "${MISSING[@]}"
# Headers help eBPF compile on some kernels
sudo apt-get install -y -qq "linux-headers-$(uname -r)" 2>/dev/null || \
    sudo apt-get install -y -qq linux-headers-generic 2>/dev/null || true

echo "Done. Restart Telemetry Agent and DPI Service tabs."
