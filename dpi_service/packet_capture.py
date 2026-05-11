from scapy.all import sniff, conf

<<<<<<< HEAD
def start_capture(callback, iface=None):
    iface = iface or conf.iface
    print(f"Starting DPI packet capture on interface: {iface}")
=======
def start_capture(callback):

    print("Starting packet capture...")

    iface = conf.iface

    print(f"Using interface: {iface}")
>>>>>>> 249fcebef8fc6fb9b6ee6caf55a4990337cf304a

    sniff(
        prn=callback,
        store=False,
<<<<<<< HEAD
        filter="tcp or udp",   # Now captures both TCP and UDP (DNS, QUIC, etc.)
=======
        filter="tcp",
>>>>>>> 249fcebef8fc6fb9b6ee6caf55a4990337cf304a
        iface=iface
    )