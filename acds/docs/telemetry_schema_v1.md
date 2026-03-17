# Telemetry JSON Schema (Version 1.0)
**Contract valid for ACDS DPI Team Integration**

## Overview
This document defines the strict `telemetry.raw` schema produced by the eBPF Telemetry Agent. The DPI team must build their parsers against this exact contract to ensure safe ML feature extraction downwards.

### Schema: `v1.0`

```json
{
  "schema_version": "1.0",
  "timestamp": 1700000000,
  "kernel_timestamp_ns": 12345678901234,
  "host_id": "node-01",
  "pid": 4321,
  "process_name": "curl",
  "syscall": "connect",
  "container_id": "abcd1234",
  "success": true,
  "return_code": 0,
  "protocol": "TCP",
  "dst_port": 443,
  "src_port": 45000,
  "dst_ip": "8.8.8.8",
  "src_ip": "10.0.0.5"
}
```

## Field Guarantees & Types

| Field                 | Type      | Required? | Description |
|-----------------------|-----------|-----------|-------------|
| `schema_version`      | String    | Yes       | Hardcoded to `"1.0"`. Reject if it drifts. |
| `timestamp`           | Integer   | Yes       | Epoch seconds of the event execution time. |
| `kernel_timestamp_ns` | Integer   | Yes       | Raw monotonic ktime mapping avoiding userland skew. |
| `host_id`             | String    | Yes       | Hostname string representing the originating node. |
| `pid`                 | Integer   | Yes       | Process ID responsible for the syscall execution. |
| `process_name`        | String    | Yes       | Max 16 character `comm` process name (e.g., `nginx`). |
| `syscall`             | String    | Yes       | Enum: `"connect"` or `"execve"`. |
| `container_id`        | String    | No        | Max 12 char hex string representing the runtime container. Empty string `""` if process is not containerized. |

### `connect` Specific Fields

If `syscall` == `"connect"`, the following fields are strictly present:

| Field                 | Type      | Description |
|-----------------------|-----------|-------------|
| `success`             | Boolean   | strictly `true` *only* if `return_code == 0`. DPI must interpret this. |
| `return_code`         | Integer   | The unmodified kernel `retval`. Example: `-115` (`EINPROGRESS`) for non-blocking sockets. |
| `protocol`            | String    | `"TCP"`, `"UDP"`, or raw integer string for unknowns. Derived natively from `sk->sk_protocol`. |
| `dst_port`            | Integer   | Destination network port in host byte order. |
| `src_port`            | Integer   | Source port assigned to the socket. |
| `dst_ip`              | String    | Dotted quadrinomial IPv4 or standard IPv6 representation notation. |
| `src_ip`              | String    | Valid source IP resolved via routing bound to the hook (`saddr`). |

## Implementation Constraints & Known Limitations

### 1. UDP Connect Semantics (Critical for DPI/ML)
UDP is a connectionless protocol. The `sys_connect` intercept for UDP does **not** signify a completed 3-way handshake or remote reachability. 
* A `success: true` for a UDP connection merely means the kernel bounded the socket structure successfully to a remote address configuration.
* The ML pipeline **must not** construct "connection established" trust models implicitly based heavily on UDP `connect` successes alone without secondary traffic flow verification (if DPI supports payload volume mapping). 

### 2. Byte Orders
* Internal structs like `skc_dport` represent integers strictly in network byte order mappings from kernel. The agent handles conversions (`ntohs`). Do NOT attempt secondary byte order parsing conversions in DPI space. 

### 3. Asynchrony
Events are written to Kafka via immediately polling userspace queues without explicit linger block batching to drive latency downwards. They are not intrinsically strictly ordered by Kafka insertion timestamps; DPI temporal clustering should rely exclusively on `kernel_timestamp_ns`.
