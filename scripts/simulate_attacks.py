#!/usr/bin/env python3
"""
simulate_attacks.py — ACDS Attack Simulator

Mimics various attack patterns to trigger ML alerts and populate the Attack Graph.
Patterns:
1. Port Scanning (Vertical)
2. Host Scanning (Horizontal/Lateral Movement)
3. Data Exfiltration (High Volume/Entropy)
4. C2 Beaconing (Low Frequency/Small Packets)

Usage:
    sudo python3 scripts/simulate_attacks.py --type [scan|exfil|c2|lateral|all]
"""

import socket
import time
import random
import os
import sys
import argparse
import shutil
import threading
from typing import List

# Try to import setproctitle if available, otherwise fallback
try:
    from setproctitle import setproctitle
except ImportError:
    def setproctitle(title):
        pass

# --- Configuration ---
TARGET_EXTERNAL = "8.8.8.8"
TARGET_INTERNAL = "127.0.0.1"
DEFAULT_DURATION = 30  # seconds per attack

def print_banner(text):
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)

def rename_process(name: str):
    """
    Attempts to rename the current process for Telemetry visibility.
    In ACDS, the Telemetry Agent captures the process name from the kernel.
    """
    print(f"[*] Simulating as process: {name}")
    setproctitle(name)
    # On Linux, we can also try to write to /proc/self/comm if we have permissions
    try:
        with open("/proc/self/comm", "w") as f:
            f.write(name)
    except:
        pass

def simulate_port_scan(target: str, name: str = "scanner_bolt"):
    """Vertical Port Scan: Connect to many ports on one IP."""
    rename_process(name)
    print(f"[*] Starting Port Scan on {target}...")
    
    # Common ports to scan
    ports = list(range(20, 100)) + [443, 8080, 8443, 3389, 4444, 1337]
    random.shuffle(ports)

    for port in ports[:50]:  # Scan 50 ports
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.1)
            s.connect((target, port))
            print(f"  [+] Port {port} OPEN")
            s.close()
        except:
            pass
        time.sleep(0.05)
    print("[+] Port Scan complete.")

def simulate_exfiltration(target: str, port: int = 443, name: str = "exfiltrator_prime"):
    """Data Exfiltration: Send large, high-entropy payloads."""
    rename_process(name)
    print(f"[*] Starting Data Exfiltration to {target}:{port}...")
    
    # We don't actually need a server to listen, we just need to try and send data
    # to trigger the DPI features (packet size, entropy, burst rate).
    # However, for the Telemetry Agent to see a connection, it must at least attempt connect.
    
    try:
        # Generate random high-entropy data
        chunk_size = 1450 # Large packet size
        chunks = 20
        
        for i in range(chunks):
            data = os.urandom(chunk_size)
            # Use UDP for "fire and forget" to trigger DPI without needing a handshake
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.sendto(data, (target, port))
            if i % 5 == 0:
                print(f"  [>] Sent {i*chunk_size} bytes...")
            time.sleep(0.1)
    except Exception as e:
        print(f"  [!] Error: {e}")
        
    print("[+] Exfiltration simulation complete.")

def simulate_c2_beacon(target: str, name: str = "malware_beacon"):
    """C2 Beaconing: Periodic small packets."""
    rename_process(name)
    print(f"[*] Starting C2 Beaconing to {target}...")
    
    # Small packets, regular intervals
    for i in range(10):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            # Try to connect to trigger the syscall
            try:
                s.connect((target, 80))
            except:
                pass 
            s.close()
            print(f"  [o] Beacon {i+1} sent.")
        except:
            pass
        time.sleep(2) # 2 second interval
    print("[+] C2 Beaconing complete.")

def simulate_lateral_movement(name: str = "pivoter_tool"):
    """Lateral Movement: Connect to multiple IPs."""
    rename_process(name)
    print(f"[*] Starting Lateral Movement simulation...")
    
    # Range of internal-looking IPs
    base_ip = "192.168.1."
    for i in range(1, 15):
        target = base_ip + str(i)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.05)
            # Trigger 'connect' syscall
            try:
                s.connect((target, 22)) # SSH
            except:
                pass
            s.close()
            print(f"  [->] Probing {target}...")
        except:
            pass
        time.sleep(0.1)
    print("[+] Lateral Movement simulation complete.")

def run_all():
    print_banner("ACDS FULL ATTACK CAMPAIGN")
    
    # Run in sequence to keep logs clear
    simulate_port_scan(TARGET_EXTERNAL, "scanner_v1")
    time.sleep(2)
    simulate_lateral_movement("pivoter_v1")
    time.sleep(2)
    simulate_exfiltration(TARGET_EXTERNAL, 443, "exfiltrator_v1")
    time.sleep(2)
    simulate_c2_beacon(TARGET_EXTERNAL, "backdoor_v1")
    
    print_banner("CAMPAIGN COMPLETE - CHECK UI DASHBOARD")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ACDS Attack Simulator")
    parser.add_argument("--type", choices=["scan", "exfil", "c2", "lateral", "all"], default="all",
                        help="Type of attack to simulate")
    parser.add_argument("--target", default=TARGET_EXTERNAL, help="Target IP for attacks")
    
    args = parser.parse_args()
    
    # Check for root/admin (handle Windows compatibility)
    is_root = False
    try:
        is_root = os.getuid() == 0
    except AttributeError:
        # Windows fallback
        import ctypes
        try:
            is_root = ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            is_root = False

    if not is_root:
        print("[!] Warning: Running without root/admin privileges. Telemetry Agent may not see process names correctly.")
        print("[!] Recommendation: Run inside WSL2 with 'sudo python3 scripts/simulate_attacks.py'")
        time.sleep(2)

    if args.type == "scan":
        simulate_port_scan(args.target)
    elif args.type == "exfil":
        simulate_exfiltration(args.target)
    elif args.type == "c2":
        simulate_c2_beacon(args.target)
    elif args.type == "lateral":
        simulate_lateral_movement()
    else:
        run_all()
