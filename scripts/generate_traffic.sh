#!/usr/bin/env bash

echo "============================================="
echo " ACDS Telemetry: Continuous Traffic Generator"
echo "============================================="
echo "Generating various types of network packets..."
echo "Press Ctrl+C to stop."
echo ""

while true; do
    curl -s -o /dev/null https://google.com 2>&1
    curl -s -o /dev/null https://cloudflare.com 2>&1
    ping -c 1 8.8.8.8 > /dev/null 2>&1
    ping -c 1 1.1.1.1 > /dev/null 2>&1
    nslookup example.com > /dev/null 2>&1
    nslookup github.com > /dev/null 2>&1
    echo -n "."
    sleep 1
done
