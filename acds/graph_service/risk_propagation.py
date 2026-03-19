"""
risk_propagation.py — Time-decayed risk propagation across the ACDS Attack Graph.

Formula:
    node_risk = max(direct_risk, max(neighbor_risk * exp(-lambda * age_seconds)))

    lambda = 0.001   →  half-life ≈ 693 s ≈ 11.5 minutes

Also provides a TTL cleanup that removes nodes and edges older than 24 hours.
"""

import logging
import time

from neo4j_client import Neo4jClient

log = logging.getLogger("graph_service.risk")

LAMBDA = 0.001  # decay constant
TTL_SECONDS = 86400  # 24 hours


# ── Risk propagation ────────────────────────────────────────────────

PROPAGATION_QUERY = """
// 1-hop propagation: for every node with risk > 0, push decayed risk to neighbors
MATCH (src)-[r]-(neighbor)
WHERE src.risk_score > 0 AND src.last_seen IS NOT NULL
WITH neighbor,
     src.risk_score * exp(-0.001 * ($now - src.last_seen)) AS decayed_risk
WITH neighbor, max(decayed_risk) AS best_neighbor_risk
WHERE best_neighbor_risk > coalesce(neighbor.risk_score, 0)
SET neighbor.risk_score = best_neighbor_risk
RETURN count(neighbor) AS updated_1hop
"""

PROPAGATION_2HOP_QUERY = """
// 2-hop propagation (weaker): push with squared decay
MATCH (src)-[]-()-[]-(target)
WHERE src.risk_score > 0 AND src.last_seen IS NOT NULL
WITH target,
     src.risk_score * exp(-0.001 * 2 * ($now - src.last_seen)) AS decayed_risk
WITH target, max(decayed_risk) AS best_2hop_risk
WHERE best_2hop_risk > coalesce(target.risk_score, 0)
SET target.risk_score = best_2hop_risk
RETURN count(target) AS updated_2hop
"""


async def propagate_risk(neo4j_client: Neo4jClient) -> dict:
    """
    Run time-decayed risk propagation (1-hop then 2-hop).
    Returns a summary dict with counts of updated nodes.
    """
    now = time.time()
    try:
        result_1 = await neo4j_client.execute_write(PROPAGATION_QUERY, {"now": now})
        updated_1 = result_1[0]["updated_1hop"] if result_1 else 0

        result_2 = await neo4j_client.execute_write(PROPAGATION_2HOP_QUERY, {"now": now})
        updated_2 = result_2[0]["updated_2hop"] if result_2 else 0

        if updated_1 or updated_2:
            log.info("Risk propagation: 1-hop=%d, 2-hop=%d nodes updated", updated_1, updated_2)

        return {"updated_1hop": updated_1, "updated_2hop": updated_2}
    except Exception as e:
        log.error("Risk propagation failed: %s", e)
        return {"error": str(e)}


# ── TTL cleanup ─────────────────────────────────────────────────────

CLEANUP_EDGES_QUERY = """
MATCH ()-[r]-()
WHERE r.timestamp IS NOT NULL AND r.timestamp < $cutoff
DELETE r
RETURN count(r) AS deleted_edges
"""

CLEANUP_NODES_QUERY = """
MATCH (n)
WHERE n.last_seen IS NOT NULL AND n.last_seen < $cutoff
DETACH DELETE n
RETURN count(n) AS deleted_nodes
"""


async def ttl_cleanup(neo4j_client: Neo4jClient) -> dict:
    """Remove nodes and edges older than 24 hours."""
    cutoff = time.time() - TTL_SECONDS
    try:
        edge_result = await neo4j_client.execute_write(CLEANUP_EDGES_QUERY, {"cutoff": cutoff})
        deleted_edges = edge_result[0]["deleted_edges"] if edge_result else 0

        node_result = await neo4j_client.execute_write(CLEANUP_NODES_QUERY, {"cutoff": cutoff})
        deleted_nodes = node_result[0]["deleted_nodes"] if node_result else 0

        if deleted_edges or deleted_nodes:
            log.info("TTL cleanup: %d edges, %d nodes removed", deleted_edges, deleted_nodes)

        return {"deleted_edges": deleted_edges, "deleted_nodes": deleted_nodes}
    except Exception as e:
        log.error("TTL cleanup failed: %s", e)
        return {"error": str(e)}
