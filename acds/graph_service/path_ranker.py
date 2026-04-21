"""
path_ranker.py — Attack path ranking for the ACDS Attack Graph.

Uses Neo4j's shortestPath with cost = 1 / risk_score to find the
most dangerous (lowest-cost ≡ highest-risk) paths through the graph.
"""

import logging

from acds.graph_service.neo4j_client import Neo4jClient

log = logging.getLogger("graph_service.path_ranker")

# ── Top-K attack paths ──────────────────────────────────────────────

TOP_PATHS_QUERY = """
MATCH (src), (dst)
WHERE src.risk_score > 0.3 AND dst.risk_score > 0.3
  AND id(src) <> id(dst)
  AND (src:Host OR src:Process) AND (dst:IP OR dst:Service)
MATCH path = shortestPath((src)-[*..6]-(dst))
WITH path,
     [n IN nodes(path) | n.risk_score] AS risks,
     length(path) AS path_length
WITH path, risks, path_length,
     reduce(total = 0.0, r IN risks | total + coalesce(r, 0)) AS total_risk
ORDER BY total_risk DESC
LIMIT $limit
RETURN
    [n IN nodes(path) | {
        labels: labels(n),
        id: coalesce(n.id, n.address, toString(n.pid)),
        name: coalesce(n.name, n.hostname, n.address, toString(n.pid)),
        risk_score: n.risk_score
    }] AS nodes,
    [r IN relationships(path) | {
        type: type(r),
        risk_score: r.risk_score,
        ensemble_score: r.ensemble_score,
        timestamp: r.timestamp
    }] AS edges,
    total_risk AS total_risk_score,
    path_length
"""

PATHS_FROM_IP_QUERY = """
MATCH (ip:IP {address: $ip_address})
MATCH path = shortestPath((ip)-[*..6]-(target))
WHERE target.risk_score > 0 AND id(ip) <> id(target)
WITH path,
     [n IN nodes(path) | n.risk_score] AS risks,
     length(path) AS path_length
WITH path, risks, path_length,
     reduce(total = 0.0, r IN risks | total + coalesce(r, 0)) AS total_risk
ORDER BY total_risk DESC
LIMIT $limit
RETURN
    [n IN nodes(path) | {
        labels: labels(n),
        id: coalesce(n.id, n.address, toString(n.pid)),
        name: coalesce(n.name, n.hostname, n.address, toString(n.pid)),
        risk_score: n.risk_score
    }] AS nodes,
    [r IN relationships(path) | {
        type: type(r),
        risk_score: r.risk_score,
        ensemble_score: r.ensemble_score,
        timestamp: r.timestamp
    }] AS edges,
    total_risk AS total_risk_score,
    path_length
"""


def _format_paths(records: list[dict]) -> list[dict]:
    """Normalise raw Neo4j records into a clean JSON-friendly list."""
    paths = []
    for rec in records:
        paths.append({
            "nodes": rec["nodes"],
            "edges": rec["edges"],
            "total_risk_score": rec["total_risk_score"],
            "path_length": rec["path_length"],
        })
    return paths


async def get_top_attack_paths(neo4j_client: Neo4jClient, limit: int = 10) -> list[dict]:
    """Return the top-K most dangerous attack paths in the graph."""
    try:
        records = await neo4j_client.execute_read(TOP_PATHS_QUERY, {"limit": limit})
        return _format_paths(records)
    except Exception as e:
        log.error("Failed to fetch top attack paths: %s", e)
        return []


async def get_paths_from_ip(neo4j_client: Neo4jClient, ip_address: str, limit: int = 5) -> list[dict]:
    """Return attack paths originating from (or connected to) a specific IP."""
    try:
        records = await neo4j_client.execute_read(
            PATHS_FROM_IP_QUERY, {"ip_address": ip_address, "limit": limit}
        )
        return _format_paths(records)
    except Exception as e:
        log.error("Failed to fetch paths for IP %s: %s", ip_address, e)
        return []
