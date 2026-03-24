import time
from collections import OrderedDict

FLOW_TIMEOUT = 10
MAX_FLOWS = 10000   # Memory safety cap

# LRU-style ordered dict — oldest entries at front
flows = OrderedDict()          # flow_key → [packets]
flow_last_seen = OrderedDict() # flow_key → timestamp


def get_flow_key(packet):
    """
    Returns a canonical bidirectional flow key:
    ((ip_lo, port_lo), (ip_hi, port_hi), proto)
    Bidirectional: A→B and B→A map to the SAME key.
    """
    if not packet.haslayer("IP"):
        return None

    src = packet["IP"].src
    dst = packet["IP"].dst
    proto = packet["IP"].proto

    # Get ports (works for both TCP and UDP)
    transport = packet["IP"].payload
    sport = getattr(transport, "sport", 0)
    dport = getattr(transport, "dport", 0)

    # Normalize to canonical bidirectional form
    endpoint_a = (src, sport)
    endpoint_b = (dst, dport)
    lo, hi = (endpoint_a, endpoint_b) if endpoint_a <= endpoint_b else (endpoint_b, endpoint_a)

    return (lo[0], lo[1], hi[0], hi[1], proto)


def add_packet(packet):
    key = get_flow_key(packet)
    if key is None:
        return None

    # LRU eviction if at capacity
    if key not in flows and len(flows) >= MAX_FLOWS:
        oldest_key = next(iter(flows))
        flows.pop(oldest_key, None)
        flow_last_seen.pop(oldest_key, None)

    if key not in flows:
        flows[key] = []

    flows[key].append(packet)
    flow_last_seen[key] = time.time()

    # Move to end (most recently used)
    flows.move_to_end(key)
    flow_last_seen.move_to_end(key)

    return key


def get_expired_flows():
    now = time.time()
    expired = []
    for key, t in list(flow_last_seen.items()):
        if now - t > FLOW_TIMEOUT:
            expired.append(key)
    return expired