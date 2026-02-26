from scapy.all import sniff, conf

def start_capture(callback):

    print("Starting packet capture...")

    iface = conf.iface

    print(f"Using interface: {iface}")

    sniff(
        prn=callback,
        store=False,
        filter="tcp",
        iface=iface
    )