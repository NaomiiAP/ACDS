import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { GitBranch, Network, AlertTriangle, ChevronRight, ChevronDown, Circle, Minus, RefreshCw } from 'lucide-react';

const GRAPH_API = 'http://localhost:8100/api/graph';
const CARD_BG = '#111620';
const CARD_BORDER = 'rgba(255,255,255,0.07)';

const NODE_COLORS = {
    host: '#3b82f6',
    container: '#06b6d4',
    process: '#10b981',
    ip: '#6b7280',
    default: '#64748b',
};

const RISK = {
    high: { color: '#ef4444', bg: 'rgba(239,68,68,0.12)', border: 'rgba(239,68,68,0.3)', label: 'HIGH' },
    medium: { color: '#f59e0b', bg: 'rgba(245,158,11,0.10)', border: 'rgba(245,158,11,0.3)', label: 'MEDIUM' },
    low: { color: '#10b981', bg: 'rgba(16,185,129,0.08)', border: 'rgba(16,185,129,0.2)', label: 'LOW' },
};

function riskLevel(score) {
    if (score >= 0.7) return 'high';
    if (score >= 0.4) return 'medium';
    return 'low';
}

function RiskBadge({ level }) {
    const r = RISK[level] || RISK.low;
    return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold"
            style={{ background: r.bg, color: r.color, border: `1px solid ${r.border}` }}>
            {level === 'high' && <AlertTriangle className="h-3 w-3" />}
            {r.label}
        </span>
    );
}

/* ─── Simple Force-Directed SVG Graph ─── */
function ForceGraph({ nodes, edges }) {
    const svgRef = useRef(null);
    const animRef = useRef(null);
    const [positions, setPositions] = useState([]);
    const [hoveredNode, setHoveredNode] = useState(null);
    const [dimensions, setDimensions] = useState({ width: 900, height: 500 });

    // Initialize positions
    useEffect(() => {
        if (!nodes || nodes.length === 0) return;

        const w = dimensions.width;
        const h = dimensions.height;
        const initial = nodes.map((n, i) => ({
            ...n,
            x: w / 2 + (Math.random() - 0.5) * w * 0.6,
            y: h / 2 + (Math.random() - 0.5) * h * 0.6,
            vx: 0,
            vy: 0,
        }));
        setPositions(initial);
    }, [nodes, dimensions]);

    // Force simulation
    useEffect(() => {
        if (positions.length === 0 || !edges) return;

        let running = true;
        let iter = 0;
        const maxIter = 200;
        const nodeMap = {};
        positions.forEach((p, i) => { nodeMap[p.id] = i; });

        function simulate() {
            if (!running || iter >= maxIter) return;
            iter++;

            const pos = positions.map(p => ({ ...p }));
            const w = dimensions.width;
            const h = dimensions.height;

            // Repulsive forces (nodes push each other away)
            for (let i = 0; i < pos.length; i++) {
                for (let j = i + 1; j < pos.length; j++) {
                    let dx = pos[j].x - pos[i].x;
                    let dy = pos[j].y - pos[i].y;
                    let dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    let force = 5000 / (dist * dist);
                    let fx = (dx / dist) * force;
                    let fy = (dy / dist) * force;
                    pos[i].vx -= fx;
                    pos[i].vy -= fy;
                    pos[j].vx += fx;
                    pos[j].vy += fy;
                }
            }

            // Attractive forces (edges pull connected nodes together)
            edges.forEach(e => {
                const si = nodeMap[e.source];
                const ti = nodeMap[e.target];
                if (si === undefined || ti === undefined) return;
                let dx = pos[ti].x - pos[si].x;
                let dy = pos[ti].y - pos[si].y;
                let dist = Math.sqrt(dx * dx + dy * dy) || 1;
                let force = (dist - 120) * 0.01;
                let fx = (dx / dist) * force;
                let fy = (dy / dist) * force;
                pos[si].vx += fx;
                pos[si].vy += fy;
                pos[ti].vx -= fx;
                pos[ti].vy -= fy;
            });

            // Center gravity
            pos.forEach(p => {
                p.vx += (w / 2 - p.x) * 0.002;
                p.vy += (h / 2 - p.y) * 0.002;
            });

            // Apply velocities with damping
            const damping = 0.85;
            pos.forEach(p => {
                p.vx *= damping;
                p.vy *= damping;
                p.x += p.vx;
                p.y += p.vy;
                // Clamp to bounds
                p.x = Math.max(30, Math.min(w - 30, p.x));
                p.y = Math.max(30, Math.min(h - 30, p.y));
            });

            setPositions(pos);
            animRef.current = requestAnimationFrame(simulate);
        }

        animRef.current = requestAnimationFrame(simulate);
        return () => {
            running = false;
            if (animRef.current) cancelAnimationFrame(animRef.current);
        };
    }, [positions.length]); // only run once when positions are initialized

    // Resize observer
    useEffect(() => {
        const container = svgRef.current?.parentElement;
        if (!container) return;
        const observer = new ResizeObserver(entries => {
            for (const entry of entries) {
                setDimensions({ width: entry.contentRect.width, height: Math.max(450, entry.contentRect.height) });
            }
        });
        observer.observe(container);
        return () => observer.disconnect();
    }, []);

    const posMap = useMemo(() => {
        const m = {};
        positions.forEach(p => { m[p.id] = p; });
        return m;
    }, [positions]);

    if (!nodes || nodes.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-24 gap-4 text-slate-600">
                <Network className="h-12 w-12" />
                <p className="text-lg font-medium">No graph data yet</p>
                <p className="text-sm">Start the Attack Graph service to visualize network relationships</p>
            </div>
        );
    }

    return (
        <div className="relative w-full" style={{ height: dimensions.height }}>
            <svg ref={svgRef} width={dimensions.width} height={dimensions.height} className="w-full">
                {/* Edges */}
                {edges?.map((e, i) => {
                    const s = posMap[e.source];
                    const t = posMap[e.target];
                    if (!s || !t) return null;
                    const isSuspicious = e.type === 'SUSPICIOUS_CONNECTION' || e.label === 'SUSPICIOUS_CONNECTION';
                    return (
                        <line key={i}
                            x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                            stroke={isSuspicious ? '#ef4444' : 'rgba(255,255,255,0.1)'}
                            strokeWidth={isSuspicious ? 2 : 1}
                            strokeDasharray={isSuspicious ? '' : '4,4'}
                        />
                    );
                })}
                {/* Nodes */}
                {positions.map(node => {
                    const typeKey = (node.type || 'default').toLowerCase();
                    const color = NODE_COLORS[typeKey] || NODE_COLORS.default;
                    const radius = Math.max(6, Math.min(20, (node.risk_score || 0.1) * 25));
                    const isHovered = hoveredNode === node.id;
                    return (
                        <g key={node.id}
                            onMouseEnter={() => setHoveredNode(node.id)}
                            onMouseLeave={() => setHoveredNode(null)}
                            style={{ cursor: 'pointer' }}>
                            <circle cx={node.x} cy={node.y} r={radius + (isHovered ? 4 : 0)}
                                fill={color} fillOpacity={isHovered ? 0.4 : 0.15}
                                stroke={color} strokeWidth={isHovered ? 2 : 1} />
                            <circle cx={node.x} cy={node.y} r={3}
                                fill={color} />
                            {isHovered && (
                                <text x={node.x} y={node.y - radius - 8}
                                    textAnchor="middle" fill="white" fontSize="11" fontFamily="monospace">
                                    {node.label || node.id}
                                </text>
                            )}
                        </g>
                    );
                })}
            </svg>

            {/* Tooltip */}
            {hoveredNode && (() => {
                const node = posMap[hoveredNode];
                if (!node) return null;
                return (
                    <div className="absolute pointer-events-none rounded-xl p-3 border text-xs space-y-1"
                        style={{
                            left: Math.min(node.x + 15, dimensions.width - 200),
                            top: node.y + 15,
                            background: '#0e1117',
                            borderColor: CARD_BORDER,
                            zIndex: 10,
                        }}>
                        <p className="font-bold text-white">{node.label || node.id}</p>
                        <p className="text-slate-400">Type: <span className="text-slate-200">{node.type || '—'}</span></p>
                        <p className="text-slate-400">Risk: <span className="font-mono" style={{ color: RISK[riskLevel(node.risk_score || 0)]?.color }}>
                            {typeof node.risk_score === 'number' ? (node.risk_score * 100).toFixed(0) + '%' : '—'}
                        </span></p>
                    </div>
                );
            })()}

            {/* Legend */}
            <div className="absolute bottom-3 left-3 flex gap-3 text-xs text-slate-500">
                {Object.entries(NODE_COLORS).filter(([k]) => k !== 'default').map(([type, color]) => (
                    <div key={type} className="flex items-center gap-1.5">
                        <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
                        <span className="capitalize">{type}</span>
                    </div>
                ))}
                <div className="flex items-center gap-1.5 ml-2">
                    <div className="w-4 h-0.5 bg-red-500" />
                    <span>Suspicious</span>
                </div>
            </div>
        </div>
    );
}

/* ─── Attack Paths Table ─── */
function PathsTable({ paths }) {
    const [expanded, setExpanded] = useState(null);

    if (!paths || paths.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-24 gap-4 text-slate-600">
                <GitBranch className="h-12 w-12" />
                <p className="text-lg font-medium">No attack paths found</p>
                <p className="text-sm">Attack paths will appear once the graph service identifies risky routes</p>
            </div>
        );
    }

    return (
        <div className="rounded-2xl border overflow-hidden" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
            <table className="w-full text-sm">
                <thead>
                    <tr className="text-xs text-slate-500 uppercase tracking-wider border-b"
                        style={{ borderColor: CARD_BORDER, background: 'rgba(255,255,255,0.02)' }}>
                        <th className="px-5 py-3 text-left w-16">Rank</th>
                        <th className="px-5 py-3 text-left">Path</th>
                        <th className="px-5 py-3 text-right">Risk Score</th>
                        <th className="px-5 py-3 text-right">Length</th>
                        <th className="px-3 py-3"></th>
                    </tr>
                </thead>
                <tbody>
                    {paths.map((p, i) => {
                        const risk = riskLevel(p.total_risk_score || p.risk_score || 0);
                        const isExpanded = expanded === i;
                        const pathNodes = p.nodes || p.path || [];
                        return (
                            <React.Fragment key={i}>
                                <tr className="border-t cursor-pointer hover:bg-white/[0.025] transition-colors"
                                    style={{ borderColor: 'rgba(255,255,255,0.04)' }}
                                    onClick={() => setExpanded(isExpanded ? null : i)}>
                                    <td className="px-5 py-3 text-slate-400 font-mono">#{i + 1}</td>
                                    <td className="px-5 py-3">
                                        <div className="flex items-center gap-1 flex-wrap">
                                            {pathNodes.map((n, j) => (
                                                <React.Fragment key={j}>
                                                    <span className="px-2 py-0.5 rounded text-xs font-mono"
                                                        style={{ background: 'rgba(255,255,255,0.05)', color: '#e2e8f0' }}>
                                                        {typeof n === 'string' ? n : n.label || n.id || '?'}
                                                    </span>
                                                    {j < pathNodes.length - 1 && (
                                                        <ChevronRight className="h-3 w-3 text-slate-600 shrink-0" />
                                                    )}
                                                </React.Fragment>
                                            ))}
                                        </div>
                                    </td>
                                    <td className="px-5 py-3 text-right">
                                        <RiskBadge level={risk} />
                                    </td>
                                    <td className="px-5 py-3 text-right font-mono text-slate-400">{pathNodes.length}</td>
                                    <td className="px-3 py-3 text-slate-600">
                                        {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                                    </td>
                                </tr>
                                {isExpanded && (
                                    <tr>
                                        <td colSpan={5} className="px-5 py-4" style={{ background: 'rgba(255,255,255,0.02)' }}>
                                            <div className="space-y-2">
                                                <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Path Details</p>
                                                <div className="grid grid-cols-2 gap-3 text-sm">
                                                    <div>
                                                        <span className="text-slate-500">Total Risk Score: </span>
                                                        <span className="font-mono text-slate-200">
                                                            {(p.total_risk_score || p.risk_score || 0).toFixed(3)}
                                                        </span>
                                                    </div>
                                                    <div>
                                                        <span className="text-slate-500">Path Length: </span>
                                                        <span className="font-mono text-slate-200">{pathNodes.length} nodes</span>
                                                    </div>
                                                    {p.description && (
                                                        <div className="col-span-2">
                                                            <span className="text-slate-500">Description: </span>
                                                            <span className="text-slate-300">{p.description}</span>
                                                        </div>
                                                    )}
                                                </div>
                                                <div className="flex items-center gap-2 pt-2">
                                                    {pathNodes.map((n, j) => {
                                                        const nodeLabel = typeof n === 'string' ? n : n.label || n.id || '?';
                                                        const nodeType = typeof n === 'object' ? (n.type || '').toLowerCase() : '';
                                                        const color = NODE_COLORS[nodeType] || NODE_COLORS.default;
                                                        return (
                                                            <React.Fragment key={j}>
                                                                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs"
                                                                    style={{ borderColor: `${color}40`, background: `${color}10` }}>
                                                                    <Circle className="h-2.5 w-2.5" style={{ color, fill: color }} />
                                                                    <span className="font-mono text-slate-200">{nodeLabel}</span>
                                                                </div>
                                                                {j < pathNodes.length - 1 && <Minus className="h-3 w-3 text-slate-600" />}
                                                            </React.Fragment>
                                                        );
                                                    })}
                                                </div>
                                            </div>
                                        </td>
                                    </tr>
                                )}
                            </React.Fragment>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}

export default function AttackGraph() {
    const [view, setView] = useState('graph');
    const [summary, setSummary] = useState({ total_nodes: 0, total_edges: 0, high_risk_nodes: 0, attack_paths_found: 0 });
    const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
    const [paths, setPaths] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const fetchAll = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [summaryRes, graphRes, pathsRes] = await Promise.allSettled([
                fetch(`${GRAPH_API}/summary`),
                fetch(`${GRAPH_API}/data`),
                fetch(`${GRAPH_API}/paths`),
            ]);

            if (summaryRes.status === 'fulfilled' && summaryRes.value.ok) {
                setSummary(await summaryRes.value.json());
            }
            if (graphRes.status === 'fulfilled' && graphRes.value.ok) {
                setGraphData(await graphRes.value.json());
            }
            if (pathsRes.status === 'fulfilled' && pathsRes.value.ok) {
                setPaths(await pathsRes.value.json());
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchAll();
        const interval = setInterval(fetchAll, 10000);
        return () => clearInterval(interval);
    }, [fetchAll]);

    // Sidebar: top risky entities
    const riskyNodes = useMemo(() => {
        if (!graphData.nodes) return [];
        return [...graphData.nodes]
            .filter(n => typeof n.risk_score === 'number')
            .sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0))
            .slice(0, 15);
    }, [graphData.nodes]);

    return (
        <div className="p-6 space-y-5" style={{ background: '#0a0d12', minHeight: 'calc(100vh - 64px)' }}>

            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold text-white flex items-center gap-2">
                        <GitBranch className="h-5 w-5 text-violet-400" /> Attack Graph
                    </h2>
                    <p className="text-sm text-slate-500 mt-0.5">Network topology with risk-scored nodes and attack path analysis</p>
                </div>
                <button onClick={fetchAll}
                    className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border transition-all text-slate-400 hover:text-white"
                    style={{ borderColor: CARD_BORDER, background: 'rgba(255,255,255,0.03)' }}>
                    <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
                    Refresh
                </button>
            </div>

            {/* Stat Cards */}
            <div className="grid grid-cols-4 gap-4">
                {[
                    { label: 'Total Nodes', value: summary.total_nodes || graphData.nodes?.length || 0, color: '#3b82f6', icon: <Circle className="h-5 w-5" /> },
                    { label: 'Total Edges', value: summary.total_edges || graphData.edges?.length || 0, color: '#64748b', icon: <Minus className="h-5 w-5" /> },
                    { label: 'High Risk Nodes', value: summary.high_risk_nodes || 0, color: '#ef4444', icon: <AlertTriangle className="h-5 w-5" /> },
                    { label: 'Attack Paths Found', value: summary.attack_paths_found || paths.length || 0, color: '#f59e0b', icon: <GitBranch className="h-5 w-5" /> },
                ].map(c => (
                    <div key={c.label} className="rounded-2xl p-5 border" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
                        <div className="flex items-center justify-between mb-3">
                            <p className="text-xs text-slate-500 uppercase tracking-wider">{c.label}</p>
                            <div className="w-8 h-8 rounded-lg flex items-center justify-center"
                                style={{ background: `${c.color}18`, color: c.color }}>
                                {c.icon}
                            </div>
                        </div>
                        <p className="text-3xl font-bold" style={{ color: c.color }}>{c.value}</p>
                    </div>
                ))}
            </div>

            {/* View toggle */}
            <div className="flex gap-2">
                {[
                    { key: 'graph', label: 'Graph View' },
                    { key: 'paths', label: 'Attack Paths' },
                ].map(v => (
                    <button key={v.key} onClick={() => setView(v.key)}
                        className={`px-4 py-1.5 rounded-full text-xs font-medium border transition-all ${view === v.key ? 'text-emerald-400' : 'text-slate-500 hover:text-white'}`}
                        style={{
                            borderColor: view === v.key ? 'rgba(16,185,129,0.3)' : CARD_BORDER,
                            background: view === v.key ? 'rgba(16,185,129,0.08)' : 'transparent'
                        }}>
                        {v.label}
                    </button>
                ))}
            </div>

            {error && (
                <div className="rounded-xl p-3 text-sm border"
                    style={{ background: 'rgba(239,68,68,0.06)', borderColor: 'rgba(239,68,68,0.2)', color: '#f87171' }}>
                    Failed to connect to graph service: {error}. Ensure the Attack Graph service is running on port 8100.
                </div>
            )}

            {/* Main content area */}
            <div className="flex gap-5">
                {/* Main panel */}
                <div className="flex-1 rounded-2xl border overflow-hidden" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
                    {view === 'graph' ? (
                        <ForceGraph nodes={graphData.nodes || []} edges={graphData.edges || []} />
                    ) : (
                        <PathsTable paths={Array.isArray(paths) ? paths : paths.paths || []} />
                    )}
                </div>

                {/* Sidebar: Top Risky Entities */}
                <div className="w-64 shrink-0 rounded-2xl border p-4 space-y-3 self-start"
                    style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
                    <p className="text-xs text-slate-500 uppercase tracking-wider">Top Risky Entities</p>
                    {riskyNodes.length === 0 ? (
                        <p className="text-xs text-slate-600">No risky nodes detected</p>
                    ) : (
                        <div className="space-y-2">
                            {riskyNodes.map((node, i) => {
                                const risk = riskLevel(node.risk_score || 0);
                                const r = RISK[risk];
                                const typeKey = (node.type || '').toLowerCase();
                                const nodeColor = NODE_COLORS[typeKey] || NODE_COLORS.default;
                                return (
                                    <div key={node.id || i} className="flex items-center gap-2 p-2 rounded-lg border transition-colors hover:bg-white/[0.03]"
                                        style={{ borderColor: 'rgba(255,255,255,0.04)' }}>
                                        <div className="w-2 h-2 rounded-full shrink-0" style={{ background: nodeColor }} />
                                        <div className="flex-1 min-w-0">
                                            <p className="text-xs font-mono text-slate-200 truncate">{node.label || node.id}</p>
                                            <p className="text-[10px] text-slate-500 capitalize">{node.type || '—'}</p>
                                        </div>
                                        <span className="text-xs font-mono shrink-0" style={{ color: r.color }}>
                                            {(node.risk_score * 100).toFixed(0)}%
                                        </span>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
