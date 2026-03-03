"""
state_store.py — TTL-based in-memory Active Connection Registry

Stores telemetry connect events keyed by canonical flow key.
Entries automatically expire after TTL_SECONDS (default 30s).
Capped at MAX_SIZE entries to prevent memory growth.
"""
import time
from collections import OrderedDict

TTL_SECONDS = 30
MAX_SIZE = 50_000


class TTLStore:
    """
    Simple TTL + LRU store using OrderedDict.
    Falls back cleanly without cachetools dependency.
    """

    def __init__(self, ttl: int = TTL_SECONDS, maxsize: int = MAX_SIZE):
        self._store: OrderedDict = OrderedDict()  # key → (value, expire_ts)
        self.ttl = ttl
        self.maxsize = maxsize

    def _canonical_key(self, src_ip, src_port, dst_ip, dst_port, protocol):
        """
        Normalize to bidirectional canonical key.
        Same formula as dpi_service/flow_manager.py.
        """
        proto_map = {"TCP": 6, "UDP": 17}
        proto_int = proto_map.get(str(protocol).upper(), 0)
        ep_a = (src_ip, int(src_port))
        ep_b = (dst_ip, int(dst_port))
        lo, hi = (ep_a, ep_b) if ep_a <= ep_b else (ep_b, ep_a)
        return (lo[0], lo[1], hi[0], hi[1], proto_int)

    def put(self, src_ip, src_port, dst_ip, dst_port, protocol, metadata: dict):
        key = self._canonical_key(src_ip, src_port, dst_ip, dst_port, protocol)
        expire = time.time() + self.ttl
        self._store[key] = (metadata, expire)
        self._store.move_to_end(key)
        # LRU eviction if at cap
        while len(self._store) > self.maxsize:
            self._store.popitem(last=False)

    def lookup(self, src_ip, src_port, dst_ip, dst_port, protocol):
        """Return metadata if found and not expired, else None."""
        key = self._canonical_key(src_ip, src_port, dst_ip, dst_port, protocol)
        entry = self._store.get(key)
        if entry is None:
            return None
        metadata, expire = entry
        if time.time() > expire:
            self._store.pop(key, None)
            return None
        self._store.move_to_end(key)
        return metadata

    def cleanup(self):
        """Remove all expired entries. Call periodically."""
        now = time.time()
        expired = [k for k, (_, exp) in list(self._store.items()) if now > exp]
        for k in expired:
            self._store.pop(k, None)
        return len(expired)

    def __len__(self):
        return len(self._store)


# Singleton used by the correlation service
registry = TTLStore()
