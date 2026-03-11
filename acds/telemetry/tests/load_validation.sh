#!/bin/bash
# Telemetry Agent Stress Test Simulation
# Validates eBPF perf buffer and Kafka serialization limits before DPI handoff.

echo "Starting DPI Load Verification Test..."

# Trigger 5000 rapid connects to validate buffer handling
# and measure Kafka/Zookeeper performance under high event volume.
echo "Spawning 5000 connection requests sequentially..."
for i in {1..5000}; do 
    # Use timeout to aggressively close the socket immediately post-SYN 
    timeout 0.1 curl -s http://example.com > /dev/null 2>&1 & 
done

echo "Waiting for background requests to finalize..."
wait

echo "Background connections dispatched."
echo ""
echo "VALIDATION CHECKLIST FOR ANALYST:"
echo "[ ] Did the agent.py console report any 'BufferError' or 'Lost Events'?"
echo "[ ] Run 'kafka-console-consumer --topic telemetry.raw --from-beginning' and verify rapid JSON ingestion."
echo "[ ] Verify 'daddr' fields correctly resolved without crashing the verifier."
echo "Test complete."
