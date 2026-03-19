"""
neo4j_client.py — Async Neo4j driver wrapper for the ACDS Attack Graph Service.

Provides execute_write / execute_read transaction helpers and
connection lifecycle management.
"""

import logging
import os

from neo4j import AsyncGraphDatabase

log = logging.getLogger("graph_service.neo4j")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "acds_password")


class Neo4jClient:
    """Thin async wrapper around the Neo4j Python driver."""

    def __init__(
        self,
        uri: str = NEO4J_URI,
        user: str = NEO4J_USER,
        password: str = NEO4J_PASSWORD,
    ):
        self._driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        log.info("Neo4j driver created for %s", uri)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    async def verify_connectivity(self) -> None:
        """Verify that the driver can reach the Neo4j server."""
        await self._driver.verify_connectivity()
        log.info("Neo4j connectivity verified")

    async def execute_write(self, query: str, params: dict | None = None) -> list[dict]:
        """Run a write transaction and return result records as dicts."""
        async with self._driver.session() as session:
            result = await session.run(query, parameters=params or {})
            records = [record.data() async for record in result]
            return records

    async def execute_read(self, query: str, params: dict | None = None) -> list[dict]:
        """Run a read transaction and return result records as dicts."""
        async with self._driver.session() as session:
            result = await session.run(query, parameters=params or {})
            records = [record.data() async for record in result]
            return records

    async def close(self) -> None:
        """Gracefully close the driver."""
        await self._driver.close()
        log.info("Neo4j driver closed")
