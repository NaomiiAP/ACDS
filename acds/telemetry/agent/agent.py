import os
import sys
import ctypes
import time
import socket
import struct
import logging

try:
    from bcc import BPF
except ImportError:
    print("FATAL: bcc module not found. Did you install bpfcc-tools / python3-bcc?", file=sys.stderr)
    sys.exit(1)

from kafka_producer import TelemetryProducer
from container_mapper import get_container_id
from config import HOST_ID, SCHEMA_VERSION

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] [%(asctime)s] %(message)s")

# Calculate system boot time offset to remap kernel nanoseconds directly to True Epoch
BOOT_TIME_OFFSET_NS = time.time_ns() - int(time.clock_gettime(time.CLOCK_BOOTTIME) * 1e9)

# Global pointer to Kafka Producer instance
producer = None

SYSCALL_MAP = {
    1: "connect",
    2: "execve"
}

def inet_ntoa(addr):
    """ Converts packed 32-bit IPv4 integer to string representation """
    return socket.inet_ntoa(struct.pack("<I", addr))

def inet_ntop_v6(addr):
    """ Converts packed 128-bit IPv6 bytes to string representation """
    return socket.inet_ntop(socket.AF_INET6, bytes(addr))


class Event(ctypes.Structure):
    _pack_ = 1  # Explicit match with padding handled in C!
    _fields_ = [
        ("timestamp", ctypes.c_uint64),
        ("pid", ctypes.c_uint32),
        ("syscall", ctypes.c_uint32),
        ("comm", ctypes.c_char * 16),
        ("saddr", ctypes.c_uint32),
        ("daddr", ctypes.c_uint32),
        ("saddr_v6", ctypes.c_ubyte * 16),
        ("daddr_v6", ctypes.c_ubyte * 16),
        ("sport", ctypes.c_uint16),
        ("dport", ctypes.c_uint16),
        ("retval", ctypes.c_uint32),
        ("cgroup_id", ctypes.c_uint64),
        ("is_ipv6", ctypes.c_uint8),
        ("protocol", ctypes.c_uint8),
        ("_pad", ctypes.c_uint8 * 6)
    ]

def handle_event(cpu, data, size):
    """
    Callback fired by bcc for each perf buffer submission from kernel space.
    Packs C struct to Python dict and pushes to Kafka.
    """
    event = ctypes.cast(data, ctypes.POINTER(Event)).contents
    
    # Preserve precise timestamp without losing precision or risking skew
    event_epoch_ns = event.timestamp + BOOT_TIME_OFFSET_NS
    
    # Core JSON layout versioned per specs
    telemetry = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": int(event_epoch_ns / 1_000_000_000),      # Standard epoch seconds
        "kernel_timestamp_ns": event.timestamp,                 # Raw preserved kernel trace time
        "host_id": HOST_ID,
        "pid": event.pid,
        "process_name": event.comm.decode('utf-8', 'replace'),
        "syscall": SYSCALL_MAP.get(event.syscall, "unknown"),
        "container_id": get_container_id(event.pid) or ""
    }

    if event.syscall == 1:
        # Success logic should strictly observe zero return 
        telemetry["success"] = (event.retval == 0)
        telemetry["return_code"] = ctypes.c_int32(event.retval).value
        
        # Determine specific Protocol via real socket definitions
        if event.protocol == socket.IPPROTO_TCP:
            telemetry["protocol"] = "TCP"
        elif event.protocol == socket.IPPROTO_UDP:
            telemetry["protocol"] = "UDP"
        else:
            telemetry["protocol"] = str(event.protocol)
            
        telemetry["dst_port"] = socket.ntohs(event.dport)
        telemetry["src_port"] = event.sport # Extracted from sk_common, already in host byte order
        
        if event.is_ipv6 == 0:
            telemetry["dst_ip"] = inet_ntoa(event.daddr)
            telemetry["src_ip"] = inet_ntoa(event.saddr)
        else:
            telemetry["dst_ip"] = inet_ntop_v6(event.daddr_v6)
            telemetry["src_ip"] = inet_ntop_v6(event.saddr_v6)

    if producer:
        producer.produce(telemetry)

def is_lsm_hook_available():
    """ Verify if security_socket_connect is available in kallsyms """
    try:
        with open("/proc/kallsyms", "r") as f:
            for line in f:
                if "security_socket_connect" in line:
                    return True
    except Exception:
        pass
    return False

def main():
    logging.info(f"[{HOST_ID}] Starting ACDS Telemetry Agent (Python+BCC)...")
    
    bpf_source = os.path.join(os.path.dirname(__file__), "..", "ebpf", "telemetry.c")
    if not os.path.exists(bpf_source):
        logging.error(f"Cannot find eBPF C program at {bpf_source}")
        sys.exit(1)
        
    with open(bpf_source, "r") as f:
        bpf_text = f.read()
    
    try:
        logging.info("Compiling eBPF program...")
        bpf = BPF(text=bpf_text)
    except Exception as e:
        logging.error(f"Failed to compile and load eBPF code: {e}")
        sys.exit(1)

    try:
        syscall_prefix = bpf.get_syscall_prefix().decode('utf-8')
        
        # Determine hook compatibility dynamically
        if is_lsm_hook_available():
            logging.info("LSM hook security_socket_connect is available. Using precise tracking.")
            bpf.attach_kprobe(event="security_socket_connect", fn_name="trace_security_socket_connect")
        else:
            logging.warning("LSM hook not found. Falling back to sys_connect interception. Protocol tracking may be less reliable.")
            bpf.attach_kprobe(event=f"{syscall_prefix}connect", fn_name="trace_sys_connect_entry")
        
        # Extract populated parameters on hook return
        bpf.attach_kretprobe(event=f"{syscall_prefix}connect", fn_name="trace_connect_return")
        
        # Intercept processes starting
        bpf.attach_kprobe(event=f"{syscall_prefix}execve", fn_name="trace_execve")
        logging.info("Successfully attached kernel kprobes.")
    except Exception as e:
        logging.error(f"Failed to attach kprobes: {e}. Ensure you run as ROOT on a supported kernel.")
        sys.exit(1)

    global producer
    try:
        producer = TelemetryProducer()
        logging.info(f"Connected to Kafka configuration: Topic={producer.topic}")
    except Exception as e:
        logging.error(f"Failed to init Kafka producer: {e}")
        sys.exit(1)

    bpf["events"].open_perf_buffer(handle_event)
    logging.info(f"[{HOST_ID}] Agent active and polling perf buffers. Press Ctrl-C to terminate.")

    try:
        while True:
            bpf.perf_buffer_poll()
    except KeyboardInterrupt:
        logging.info("\nTermination requested...")
    finally:
        if producer:
            producer.flush()
        logging.info("Exited.")

if __name__ == "__main__":
    if os.geteuid() != 0:
        logging.warning("Agent is not running as root! BPF features will likely fail.")
    main()
