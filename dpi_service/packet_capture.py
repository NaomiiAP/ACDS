from scapy.all import sniff, conf

def start_capture(callback, iface=None):
    iface = iface or conf.iface
    print(f"Starting DPI packet capture on interface: {iface}")

    sniff(
        prn=callback,
        store=False,
        filter="tcp or udp",   # Now captures both TCP and UDP (DNS, QUIC, etc.)
        iface=iface
    )