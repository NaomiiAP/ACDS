"""
neo4j_client.py — Async Neo4j driver wrapper for the ACDS Attack Graph Service.

Provides execute_write / execute_read transaction helpers and
connection lifecycle management.
"""

import asyncio
import logging
import os
import threading

from neo4j import AsyncGraphDatabase

log = logging.getLogger("graph_service.neo4j")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "acds_password")


class Neo4jClient:
    """Thread-safe async wrapper around the Neo4j Python driver.
    
    Since FastAPI runs in a separate thread from the main event loop,
    we maintain drivers per-thread to avoid event loop conflicts.
    """

    def __init__(
        self,
        uri: str = NEO4J_URI,
        user: str = NEO4J_USER,
        password: str = NEO4J_PASSWORD,
    ):
        self._uri = uri
        self._user = user
        self._password = password
        self._drivers = {}  # thread_id -> driver
        self._lock = threading.Lock()
        log.info("Neo4jClient initialized for %s", uri)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_driver(self):
        """Get or create the driver for the current thread."""
        thread_id = threading.get_ident()
        
        if thread_id not in self._drivers:
            with self._lock:
                # Double-check after acquiring lock
                if thread_id not in self._drivers:
                    driver = AsyncGraphDatabase.driver(
                        self._uri, auth=(self._user, self._password)
                    )
                    self._drivers[thread_id] = driver
                    log.debug(f"Created Neo4j driver for thread {thread_id}")
        
        return self._drivers[thread_id]

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    async def verify_connectivity(self) -> None:
        """Verify that the driver can reach the Neo4j server."""
        driver = self._get_driver()
        await driver.verify_connectivity()
        log.info("Neo4j connectivity verified")

    async def execute_write(self, query: str, params: dict | None = None) -> list[dict]:
        """Run a write transaction and return result records as dicts."""
        driver = self._get_driver()
        async with driver.session() as session:
            result = await session.run(query, parameters=params or {})
            records = [record.data() async for record in result]
            return records

    async def execute_read(self, query: str, params: dict | None = None) -> list[dict]:
        """Run a read transaction and return result records as dicts."""
        driver = self._get_driver()
        async with driver.session() as session:
            result = await session.run(query, parameters=params or {})
            records = [record.data() async for record in result]
            return records

    async def close(self) -> None:
        """Gracefully close all drivers."""
        with self._lock:
            for thread_id, driver in list(self._drivers.items()):
                try:
                    await driver.close()
                    log.info(f"Closed Neo4j driver for thread {thread_id}")
                except Exception as e:
                    log.warning(f"Error closing driver for thread {thread_id}: {e}")
            self._drivers.clear()
