#include <uapi/linux/ptrace.h>
#include <uapi/linux/in.h>
#include <uapi/linux/in6.h>
#include <linux/socket.h>
#include <net/sock.h>
#include <bcc/proto.h>

/* Manually define fixed-width types (NO stdint.h allowed in BPF) */
typedef unsigned char       u8;
typedef unsigned short      u16;
typedef unsigned int        u32;
typedef unsigned long long  u64;

#define TASK_COMM_LEN 16

/* Structure sent to userspace */
struct telemetry_event_t {
    u64 timestamp;
    u32 pid;
    u32 syscall;
    char comm[TASK_COMM_LEN];

    u32 saddr;
    u32 daddr;
    u8  saddr_v6[16];
    u8  daddr_v6[16];

    u16 sport;
    u16 dport;

    u32 retval;
    u64 cgroup_id;

    u8  is_ipv6;
    u8  protocol;
    u8  _pad[6];   /* explicit alignment padding */
};

/* LRU map for tracking sockets */
BPF_HASH(active_socks, u32, u64, 10240);
BPF_PERF_OUTPUT(events);

/* security_socket_connect hook */
int trace_security_socket_connect(struct pt_regs *ctx,
                                  struct socket *sock,
                                  struct sockaddr *address,
                                  int addrlen)
{
    u32 pid = bpf_get_current_pid_tgid() >> 32;

    struct sock *sk = NULL;
    bpf_probe_read_kernel(&sk, sizeof(sk), &sock->sk);

    u16 family = 0;
    bpf_probe_read_kernel(&family, sizeof(family), &address->sa_family);

    if (family != AF_INET && family != AF_INET6)
        return 0;

    u64 sk_addr = (u64)sk;
    active_socks.update(&pid, &sk_addr);

    return 0;
}

/* Fallback sys_connect entry */
int trace_sys_connect_entry(struct pt_regs *ctx,
                            int fd,
                            struct sockaddr *uservaddr,
                            int addrlen)
{
    u32 pid = bpf_get_current_pid_tgid() >> 32;

    u64 sk_addr = 0;
    active_socks.update(&pid, &sk_addr);

    return 0;
}

/* connect return probe */
int trace_connect_return(struct pt_regs *ctx)
{
    u32 pid = bpf_get_current_pid_tgid() >> 32;

    u64 *sk_addrp = active_socks.lookup(&pid);
    if (!sk_addrp)
        return 0;

    struct sock *sk = (struct sock *)(*sk_addrp);
    int ret = PT_REGS_RC(ctx);

    struct telemetry_event_t event = {};
    event.timestamp = bpf_ktime_get_ns();
    event.pid = pid;
    event.retval = ret;
    event.cgroup_id = bpf_get_current_cgroup_id();
    event.syscall = 1;

    bpf_get_current_comm(&event.comm, sizeof(event.comm));

    u16 family = 0;
    bpf_probe_read_kernel(&family, sizeof(family),
                          &sk->__sk_common.skc_family);

    if (family == AF_INET) {

        event.is_ipv6 = 0;

        bpf_probe_read_kernel(&event.saddr, sizeof(event.saddr),
                              &sk->__sk_common.skc_rcv_saddr);

        bpf_probe_read_kernel(&event.daddr, sizeof(event.daddr),
                              &sk->__sk_common.skc_daddr);

        u16 sport = 0;
        bpf_probe_read_kernel(&sport, sizeof(sport),
                              &sk->__sk_common.skc_num);

        event.sport = sport;

        bpf_probe_read_kernel(&event.dport, sizeof(event.dport),
                              &sk->__sk_common.skc_dport);

    } else if (family == AF_INET6) {

        event.is_ipv6 = 1;

        bpf_probe_read_kernel(&event.saddr_v6,
                              sizeof(event.saddr_v6),
                              &sk->__sk_common.skc_v6_rcv_saddr.in6_u.u6_addr8);

        bpf_probe_read_kernel(&event.daddr_v6,
                              sizeof(event.daddr_v6),
                              &sk->__sk_common.skc_v6_daddr.in6_u.u6_addr8);

        u16 sport = 0;
        bpf_probe_read_kernel(&sport, sizeof(sport),
                              &sk->__sk_common.skc_num);

        event.sport = sport;

        bpf_probe_read_kernel(&event.dport, sizeof(event.dport),
                              &sk->__sk_common.skc_dport);
    }

    bpf_probe_read_kernel(&event.protocol,
                          sizeof(event.protocol),
                          &sk->sk_protocol);

    events.perf_submit(ctx, &event, sizeof(event));
    active_socks.delete(&pid);

    return 0;
}

/* execve probe */
int trace_execve(struct pt_regs *ctx)
{
    u32 pid = bpf_get_current_pid_tgid() >> 32;

    struct telemetry_event_t event = {};

    event.timestamp = bpf_ktime_get_ns();
    event.pid = pid;
    event.cgroup_id = bpf_get_current_cgroup_id();
    event.syscall = 2;

    bpf_get_current_comm(&event.comm, sizeof(event.comm));

    events.perf_submit(ctx, &event, sizeof(event));
    return 0;
}