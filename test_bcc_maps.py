import sys
try:
    from bcc import BPF
except ImportError as e:
    print("BCC not found:", e)
    sys.exit(1)

# Test 1: u32, u64
bpf_text1 = """
#include <linux/kconfig.h>
#include <uapi/linux/ptrace.h>
#include <linux/types.h>
#include <linux/socket.h>
#include <net/sock.h>
#include <bcc/proto.h>

BPF_LRU_HASH(active_socks, u32, u64, 10240);
int dummy(void *ctx) { return 0; }
"""

try:
    BPF(text=bpf_text1)
    print("Compilation success: u32/u64")
except Exception as e:
    print("Compilation failed: u32/u64 ->", e)

# Test 2: struct sock pointer
bpf_text2 = """
#include <linux/kconfig.h>
#include <uapi/linux/ptrace.h>
#include <linux/types.h>
#include <linux/socket.h>
#include <net/sock.h>
#include <bcc/proto.h>

BPF_LRU_HASH(active_socks, u32, struct sock *, 10240);
int dummy(void *ctx) { return 0; }
"""

try:
    BPF(text=bpf_text2)
    print("Compilation success: struct sock *")
except Exception as e:
    print("Compilation failed: struct sock * ->", e)
