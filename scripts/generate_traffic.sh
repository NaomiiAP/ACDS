#!/usr/bin/env bash

echo "============================================="
echo " ACDS Telemetry: Continuous Traffic Generator"
echo "============================================="
echo "Generating various types of network packets..."
echo "Press Ctrl+C to stop."
echo ""

# Infinite loop to create continuous background noise
while true; do
    # Generate TCP HTTP requests
    curl -s -o /dev/null https://google.com
    curl -s -o /dev/null https://cloudflare.com
    
    # Generate ICMP & UDP (DNS) traffic
    ping -c 1 8.8.8.8 > /dev/null
    ping -c 1 1.1.1.1 > /dev/null
    
    # Generate DNS Lookups
    nslookup example.com > /dev/null
    nslookup github.com > /dev/null
    
    # Print status marker so the user knows it's working
    echo -n "."
    
    # Sleep to control the rate (approx 5-10 events per sec)
    sleep 1
done
