"""
api.py — FastAPI REST endpoints for the ACDS Attack Graph Service.

Run standalone:
    uvicorn api:app --host 0.0.0.0 --port 8100

When launched from graph_main.py the app is started in-process on a
background thread so both the Kafka consumer and the API share the
same Neo4jClient instance.
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from acds.graph_service.neo4j_client import Neo4jClient
from acds.graph_service.path_ranker import get_top_attack_paths, get_paths_from_ip
from acds.graph_service.risk_propagation import propagate_risk

log = logging.getLogger("graph_service.api")

# The Neo4jClient is injected at startup (see lifespan or graph_main).
_neo4j: Neo4jClient | None = None


def set_neo4j_client(client: Neo4jClient) -> None:
    """Allow graph_main to inject a shared Neo4jClient."""
    global _neo4j
    _neo4j = client


def _get_neo4j() -> Neo4jClient:
    if _neo4j is None:
        raise RuntimeError("Neo4jClient not initialised")
    return _neo4j


# ── Lifespan (standalone mode) ──────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _neo4j
    if _neo4j is None:
        _neo4j = Neo4jClient()
        await _neo4j.verify_connectivity()
        log.info("API: Neo4j client created (standalone mode)")
    yield
    if _neo4j is not None:
        await _neo4j.close()


app = FastAPI(title="ACDS Attack Graph API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Endpoints ────────────────────────────────────────────────────────


@app.get("/api/graph/summary")
async def graph_summary():
    """Node counts by type, edge counts, and top risky entities."""
    neo = _get_neo4j()

    node_counts_q = """
    MATCH (n)
    RETURN labels(n)[0] AS label, count(n) AS cnt
    """
    edge_counts_q = """
    MATCH ()-[r]->()
    RETURN type(r) AS rel_type, count(r) AS cnt
    """
    top_risky_q = """
    MATCH (n)
    WHERE n.risk_score IS NOT NULL AND n.risk_score > 0
    RETURN labels(n)[0] AS label,
           coalesce(n.id, n.address, toString(n.pid)) AS entity_id,
           coalesce(n.name, n.hostname, n.address, toString(n.pid)) AS name,
           n.risk_score AS risk_score
    ORDER BY n.risk_score DESC
    LIMIT 10
    """

    node_counts = await neo.execute_read(node_counts_q)
    edge_counts = await neo.execute_read(edge_counts_q)
    top_risky = await neo.execute_read(top_risky_q)

    return {
        "node_counts": {r["label"]: r["cnt"] for r in node_counts},
        "edge_counts": {r["rel_type"]: r["cnt"] for r in edge_counts},
        "top_risky_entities": top_risky,
    }


@app.get("/api/graph/nodes")
async def get_nodes(
    type: Optional[str] = Query(None, description="Node label (Host, IP, Process, Container)"),
    min_risk: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=500),
):
    """Query nodes with optional type and risk filters."""
    neo = _get_neo4j()

    label_filter = f":{type}" if type else ""
    query = f"""
    MATCH (n{label_filter})
    WHERE coalesce(n.risk_score, 0) >= $min_risk
    RETURN labels(n)[0] AS label,
           coalesce(n.id, n.address, toString(n.pid)) AS entity_id,
           coalesce(n.name, n.hostname, n.address, toString(n.pid)) AS name,
           n.risk_score AS risk_score,
           n.last_seen AS last_seen
    ORDER BY n.risk_score DESC
    LIMIT $limit
    """
    records = await neo.execute_read(query, {"min_risk": min_risk, "limit": limit})
    return {"nodes": records, "count": len(records)}


@app.get("/api/graph/paths")
async def top_paths(limit: int = Query(10, ge=1, le=50)):
    """Top-K most dangerous attack paths."""
    neo = _get_neo4j()
    paths = await get_top_attack_paths(neo, limit=limit)
    return {"paths": paths, "count": len(paths)}


@app.get("/api/graph/paths/{ip}")
async def paths_from_ip(ip: str, limit: int = Query(5, ge=1, le=50)):
    """Attack paths from/to a specific IP address."""
    neo = _get_neo4j()
    paths = await get_paths_from_ip(neo, ip_address=ip, limit=limit)
    return {"ip": ip, "paths": paths, "count": len(paths)}


@app.get("/api/graph/risk/{host_id}")
async def host_risk(host_id: str):
    """Propagated risk information for a specific host."""
    neo = _get_neo4j()

    query = """
    MATCH (h:Host {id: $host_id})
    OPTIONAL MATCH (h)-[:HOSTS]->(c:Container)
    OPTIONAL MATCH (c)-[:RUNS]->(p:Process)
    OPTIONAL MATCH (p)-[r]->(ip:IP)
    RETURN h.risk_score AS host_risk,
           h.last_seen AS last_seen,
           h.event_count AS event_count,
           collect(DISTINCT {
               container_id: c.id,
               risk_score: c.risk_score
           }) AS containers,
           collect(DISTINCT {
               pid: p.pid,
               name: p.name,
               risk_score: p.risk_score
           }) AS processes,
           collect(DISTINCT {
               address: ip.address,
               risk_score: ip.risk_score,
               edge_type: type(r)
           }) AS connected_ips
    """
    records = await neo.execute_read(query, {"host_id": host_id})
    if not records:
        return {"error": "Host not found", "host_id": host_id}
    return {"host_id": host_id, **records[0]}


@app.get("/api/graph/data")
async def full_graph_data(max_nodes: int = Query(500, ge=1, le=2000)):
    """Full graph data for front-end visualisation (nodes + edges), capped."""
    neo = _get_neo4j()

    nodes_q = """
    MATCH (n)
    RETURN id(n) AS neo_id,
           labels(n)[0] AS label,
           coalesce(n.id, n.address, toString(n.pid)) AS entity_id,
           coalesce(n.name, n.hostname, n.address, toString(n.pid)) AS name,
           n.risk_score AS risk_score,
           n.last_seen AS last_seen
    ORDER BY n.risk_score DESC
    LIMIT $max_nodes
    """
    edges_q = """
    MATCH (a)-[r]->(b)
    WHERE id(a) IN $node_ids AND id(b) IN $node_ids
    RETURN id(a) AS source_neo_id,
           id(b) AS target_neo_id,
           type(r) AS rel_type,
           r.risk_score AS risk_score,
           r.ensemble_score AS ensemble_score,
           r.timestamp AS timestamp
    """

    nodes = await neo.execute_read(nodes_q, {"max_nodes": max_nodes})
    node_ids = [n["neo_id"] for n in nodes]

    edges = []
    if node_ids:
        edges = await neo.execute_read(edges_q, {"node_ids": node_ids})

    # Build an id-map so the front-end can reference by index
    neo_id_to_idx = {n["neo_id"]: i for i, n in enumerate(nodes)}
    formatted_edges = []
    for e in edges:
        src_idx = neo_id_to_idx.get(e["source_neo_id"])
        tgt_idx = neo_id_to_idx.get(e["target_neo_id"])
        if src_idx is not None and tgt_idx is not None:
            formatted_edges.append({
                "source": src_idx,
                "target": tgt_idx,
                "rel_type": e["rel_type"],
                "risk_score": e.get("risk_score"),
                "ensemble_score": e.get("ensemble_score"),
                "timestamp": e.get("timestamp"),
            })

    return {
        "nodes": [
            {
                "id": n["entity_id"],
                "label": n["label"],
                "name": n["name"],
                "risk_score": n["risk_score"],
                "last_seen": n["last_seen"],
            }
            for n in nodes
        ],
        "edges": formatted_edges,
        "node_count": len(nodes),
        "edge_count": len(formatted_edges),
    }
