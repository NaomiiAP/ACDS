import time

flows = {}
flow_last_seen = {}

FLOW_TIMEOUT = 10

def get_flow_key(packet):

    if not packet.haslayer("IP"):
        return None

    src = packet["IP"].src
    dst = packet["IP"].dst

    sport = getattr(packet, "sport", 0)
    dport = getattr(packet, "dport", 0)

    proto = packet["IP"].proto

    return (src, dst, sport, dport, proto)


def add_packet(packet):

    key = get_flow_key(packet)
    if key is None:
        return None

    if key not in flows:
        flows[key] = []

    flows[key].append(packet)

    flow_last_seen[key] = time.time()

    return key


def get_expired_flows():

    now = time.time()
    expired = []

    for key, t in flow_last_seen.items():
        if now - t > FLOW_TIMEOUT:
            expired.append(key)

    return expired