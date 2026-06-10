#!/usr/bin/env bash
source "$(dirname "$0")/venv.sh"
TP="$(acds_telemetry_pythonpath)"
cd "${ACDS_PROJECT_DIR}/acds/telemetry/agent"
export PYTHONPATH="${TP}"
/usr/bin/python3 -c "
from bcc import BPF
from kafka_producer import TelemetryProducer
print('Telemetry agent imports: OK')
"
