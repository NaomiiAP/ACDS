def connection_frequency(flow):
    return len(flow)

def average_packet_size(flow):

    sizes = [len(p) for p in flow]
    return sum(sizes) / len(sizes)

def inter_arrival_time(flow):

    times = [p.time for p in flow]

    if len(times) < 2:
        return 0

    gaps = [
        times[i+1] - times[i]
        for i in range(len(times)-1)
    ]

    return sum(gaps) / len(gaps)

def burst_rate(flow, threshold=0.1):

    times = [p.time for p in flow]

    burst = 0

    for i in range(len(times)-1):
        if (times[i+1] - times[i]) < threshold:
            burst += 1

    return burst

import numpy as np

def entropy(flow):

    sizes = [len(p) for p in flow]

    values, counts = np.unique(sizes, return_counts=True)

    probs = counts / counts.sum()

    return -(probs * np.log2(probs)).sum()

def tls_fingerprint(flow):

    for packet in flow:

        if packet.haslayer("Raw"):

            payload = bytes(packet["Raw"])

            if len(payload) > 5 and payload[0] == 22 and payload[1] == 3:

                version = payload[1:3].hex()

                handshake_type = payload[5]

                fp = f"TLS_{version}_HS_{handshake_type}"

                return fp

    return "none"

def extract_features(flow):

    return {
        "connection_frequency": connection_frequency(flow),
        "avg_packet_size": average_packet_size(flow),
        "entropy": entropy(flow),
        "burst_rate": burst_rate(flow),
        "inter_arrival_time": inter_arrival_time(flow),
        "tls_fingerprint": tls_fingerprint(flow)
    }