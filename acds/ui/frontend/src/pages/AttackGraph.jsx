import React, { useState, useEffect, useRef, useMemo, useCallback, useContext } from 'react';
import { GitBranch, Network, AlertTriangle, ChevronRight, ChevronDown, Circle, Minus, RefreshCw } from 'lucide-react';
import { GRAPH_API } from '../config/api';
import { DEMO_GRAPH, DEMO_PATHS, DEMO_SUMMARY } from '../data/demoAttackGraph';
import { SettingsContext } from '../context/SettingsContext';
const CARD_BG = '#0c1018';
const CARD_BORDER = 'rgba(255,255,255,0.06)';

const NODE_COLORS = {
    host: '#3b82f6',
    container: '#06b6d4',
    process: '#10b981',
    ip: '#a78bfa',
    default: '#64748b',
};

const GRAPH_STYLES = `
@keyframes flowDash { to { stroke-dashoffset: -20; } }
@keyframes pulseRing { 0%,100% { opacity:.15; transform: scale(1); } 50% { opacity:.4; transform: scale(1.5); } }
@keyframes floatDot { 0%,100% { opacity:.08; } 50% { opacity:.25; } }
`;

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

function pathRiskLevel(totalScore) {
    if (totalScore >= 2.0) return 'high';
    if (totalScore >= 1.2) return 'medium';
    return 'low';
}

function pathDescription(p) {
    if (p.description) return p.description;
    const nodes = p.nodes || p.path || [];
    const names = nodes.map(n => (typeof n === 'string' ? n : n.name || n.id || '?'));
    const label = p.edges?.[0]?.predicted_label;
    const chain = names.join(' → ');
    return label
        ? `${label} attack path: ${chain}`
        : `Suspected attack chain: ${chain}`;
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

/* ─── Cyberpunk Force-Directed SVG Graph ─── */
function ForceGraph({ nodes: rawNodes, edges: rawEdges }) {
    const svgRef = useRef(null);
    const [positions, setPositions] = useState([]);
    const [hoveredNode, setHoveredNode] = useState(null);
    const [selectedNode, setSelectedNode] = useState(null);
    const [dimensions, setDimensions] = useState({ width: 900, height: 550 });

    // Map node label->type for coloring
    const nodes = useMemo(() => (rawNodes || []).map(n => ({
        ...n, type: (n.label || n.type || 'default').toLowerCase(),
    })), [rawNodes]);

    // Keep raw edges as-is (source/target are integer indices)
    const edges = rawEdges || [];

    // Background particles
    const bgDots = useMemo(() => Array.from({length:40},()=>({
        x: Math.random()*100, y: Math.random()*100,
        r: Math.random()*1.5+0.3, dur: Math.random()*8+4, delay: Math.random()*-8,
    })), []);

    // Deduplicate edges for cleaner rendering (keep highest score per pair)
    const dedupedEdges = useMemo(() => {
        const map = new Map();
        edges.forEach(e => {
            const key = `${e.source}-${e.target}`;
            const existing = map.get(key);
            if (!existing || (e.ensemble_score||0) > (existing.ensemble_score||0)) map.set(key, e);
        });
        return Array.from(map.values());
    }, [edges]);

    // Combined: initialize positions + run force simulation once
    const simDone = useRef(false);
    useEffect(() => {
        if (!nodes || nodes.length === 0) return;

        const w = dimensions.width;
        const h = dimensions.height;
        const pos = nodes.map((n) => ({
            ...n,
            x: w / 2 + (Math.random() - 0.5) * w * 0.6,
            y: h / 2 + (Math.random() - 0.5) * h * 0.6,
            vx: 0, vy: 0,
        }));

        // Run force simulation synchronously
        for (let iter = 0; iter < 200; iter++) {
            for (let i = 0; i < pos.length; i++) {
                for (let j = i + 1; j < pos.length; j++) {
                    let dx = pos[j].x - pos[i].x;
                    let dy = pos[j].y - pos[i].y;
                    let dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    let force = 4000 / (dist * dist);
                    pos[i].vx -= (dx / dist) * force;
                    pos[i].vy -= (dy / dist) * force;
                    pos[j].vx += (dx / dist) * force;
                    pos[j].vy += (dy / dist) * force;
                }
            }
            dedupedEdges.forEach(e => {
                if (e.source >= pos.length || e.target >= pos.length) return;
                let dx = pos[e.target].x - pos[e.source].x;
                let dy = pos[e.target].y - pos[e.source].y;
                let dist = Math.sqrt(dx * dx + dy * dy) || 1;
                let force = (dist - 100) * 0.025;
                pos[e.source].vx += (dx / dist) * force;
                pos[e.source].vy += (dy / dist) * force;
                pos[e.target].vx -= (dx / dist) * force;
                pos[e.target].vy -= (dy / dist) * force;
            });
            pos.forEach(p => {
                p.vx += (w / 2 - p.x) * 0.003;
                p.vy += (h / 2 - p.y) * 0.003;
                p.vx *= 0.82;
                p.vy *= 0.82;
                p.x = Math.max(50, Math.min(w - 50, p.x + p.vx));
                p.y = Math.max(50, Math.min(h - 50, p.y + p.vy));
            });
        }

        setPositions(pos);
    }, [nodes, dedupedEdges, dimensions]);

    // Resize observer
    useEffect(() => {
        const container = svgRef.current?.parentElement;
        if (!container) return;
        const observer = new ResizeObserver(entries => {
            for (const entry of entries) {
                if (entry.contentRect.width > 0) {
                    setDimensions({ width: entry.contentRect.width, height: Math.max(500, entry.contentRect.height) });
                }
            }
        });
        observer.observe(container);
        return () => observer.disconnect();
    }, []);

    console.log('[ForceGraph] Render:', { nodes: nodes.length, positions: positions.length, hasData: nodes.length > 0 && positions.length > 0 });


    // Calculate posMap and connectedSet as plain variables (not hooks) to avoid ANY hook order issues
    const posMap = {};
    positions.forEach(p => { posMap[p.id] = p; });

    const active = selectedNode || hoveredNode;
    const connectedSet = new Set();
    if (active && positions.length > 0) {
        connectedSet.add(active);
        dedupedEdges.forEach(e => {
            const s = positions[e.source];
            const t = positions[e.target];
            if (!s || !t) return;
            if (s.id === active) connectedSet.add(t.id);
            if (t.id === active) connectedSet.add(s.id);
        });
    }

    const hasData = nodes && nodes.length > 0 && positions.length > 0;
    const activeConnectedSet = active ? connectedSet : null;


    return (
        <div className="relative w-full overflow-hidden rounded-2xl" style={{ height: dimensions.height, background: 'radial-gradient(ellipse at 50% 50%, #0a1628 0%, #050810 100%)' }}
            onClick={() => setSelectedNode(null)}>
            <style>{GRAPH_STYLES}</style>
            
            {!hasData ? (
                <div className="flex flex-col items-center justify-center h-full gap-4 text-slate-600">
                    <Network className="h-12 w-12 animate-pulse" />
                    <p className="text-lg font-medium text-slate-400">Initializing Neural Graph...</p>
                    <p className="text-sm">Run <code className="text-cyan-400">python scripts/inject_demo_alerts.py</code> to see live data</p>
                </div>
            ) : (
                <svg ref={svgRef} width={dimensions.width} height={dimensions.height} className="w-full">
                    <defs>
                        <filter id="glowSm"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
                        <filter id="edgeGlow"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
                    </defs>
                    {/* Subtle grid */}
                    {Array.from({length: Math.ceil(dimensions.width/60)}).map((_,i)=>(
                        <line key={`gv${i}`} x1={i*60} y1={0} x2={i*60} y2={dimensions.height} stroke="rgba(100,180,255,0.03)" strokeWidth="0.5"/>
                    ))}
                    {Array.from({length: Math.ceil(dimensions.height/60)}).map((_,i)=>(
                        <line key={`gh${i}`} x1={0} y1={i*60} x2={dimensions.width} y2={i*60} stroke="rgba(100,180,255,0.03)" strokeWidth="0.5"/>
                    ))}

                    {/* ── EDGES ── always visible, bold */}
                    {dedupedEdges.map((e, i) => {
                        const s = positions[e.source];
                        const t = positions[e.target];
                        if (!s || !t) return null;
                        const isSuspicious = e.rel_type === 'SUSPICIOUS_CONNECTION';
                        const isRelated = activeConnectedSet && (activeConnectedSet.has(s.id) && activeConnectedSet.has(t.id));
                        const dimmed = activeConnectedSet && !isRelated;
                        const edgeColor = isSuspicious ? '#ef4444' : '#6366f1';

                        return (
                            <g key={`e${i}`} opacity={dimmed ? 0.06 : 1}>
                                {/* Glow layer */}
                                <line x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                                    stroke={edgeColor} strokeWidth={isRelated ? 5 : 3} opacity={isRelated ? 0.3 : 0.12} filter="url(#edgeGlow)"/>
                                {/* Main line */}
                                <line x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                                    stroke={edgeColor}
                                    strokeWidth={isRelated ? 2.5 : 1.2}
                                    opacity={isRelated ? 0.9 : 0.5}
                                    strokeDasharray={isSuspicious ? '8 5' : 'none'}
                                    style={isSuspicious ? {animation:'flowDash 1s linear infinite'} : {}}
                                />
                                {/* Travelling particle on focused edges */}
                                {isRelated && (
                                    <circle r="3" fill={edgeColor} filter="url(#glowSm)">
                                        <animateMotion dur="1.5s" repeatCount="indefinite" path={`M${s.x},${s.y} L${t.x},${t.y}`}/>
                                    </circle>
                                )}
                            </g>
                        );
                    })}

                    {/* ── NODES ── solid fills, always labeled */}
                    {positions.map(node => {
                        const typeKey = (node.type || 'default').toLowerCase();
                        const color = NODE_COLORS[typeKey] || NODE_COLORS.default;
                        const risk = node.risk_score || 0;
                        const r = Math.max(8, Math.min(20, risk * 22));
                        const isHovered = hoveredNode === node.id;
                        const isSelected = selectedNode === node.id;
                        const isHighRisk = risk >= 0.7;
                        const dimmed = activeConnectedSet && !activeConnectedSet.has(node.id);

                        return (
                            <g key={node.id}
                                onMouseEnter={() => setHoveredNode(node.id)}
                                onMouseLeave={() => setHoveredNode(null)}
                                onClick={(e) => { e.stopPropagation(); setSelectedNode(isSelected ? null : node.id); }}
                                style={{ cursor: 'pointer' }}
                                opacity={dimmed ? 0.12 : 1}>
                                {/* Pulse ring for high risk */}
                                {isHighRisk && !dimmed && (
                                    <circle cx={node.x} cy={node.y} r={r*2.5} fill="none" stroke={color} strokeWidth="1" opacity="0.25"
                                        style={{animation:'pulseRing 2s ease-in-out infinite', transformOrigin:`${node.x}px ${node.y}px`}}/>
                                )}
                                {/* Outer glow */}
                                <circle cx={node.x} cy={node.y} r={r*1.6 + (isHovered||isSelected ? 8 : 0)} fill={color} opacity={0.15} filter="url(#glowSm)"/>
                                {/* Filled circle */}
                                <circle cx={node.x} cy={node.y} r={r + (isHovered||isSelected ? 4 : 0)}
                                    fill={color} fillOpacity={0.35} stroke={color} strokeWidth={isSelected ? 2.5 : isHovered ? 2 : 1} strokeOpacity={0.9}/>
                                {/* Bright core */}
                                <circle cx={node.x} cy={node.y} r={r*0.45} fill={color} opacity={0.95}/>
                                {/* Center dot */}
                                <circle cx={node.x} cy={node.y} r={1.5} fill="white" opacity="0.9"/>
                                {/* Label — always shown */}
                                <text x={node.x} y={node.y - r - 8} textAnchor="middle" fill="white" fontSize="9" fontFamily="'Inter',monospace"
                                    fontWeight={isHovered||isSelected ? '700' : '400'} opacity={dimmed ? 0.3 : (isHovered||isSelected ? 1 : 0.7)}
                                    style={{textShadow:'0 1px 6px rgba(0,0,0,0.9)', pointerEvents:'none'}}>
                                    {node.name || node.id}
                                </text>
                                {/* Type label below */}
                                {(isHovered||isSelected) && (
                                    <text x={node.x} y={node.y + r + 14} textAnchor="middle" fill={color} fontSize="8" fontFamily="monospace" opacity="0.7">
                                        {node.type?.toUpperCase()} • {(risk*100).toFixed(0)}%
                                    </text>
                                )}
                            </g>
                        );
                    })}
                </svg>
            )}

            {/* Tooltip */}
            {hoveredNode && (() => {
                const node = posMap[hoveredNode];
                if (!node) return null;
                const typeKey = (node.type||'default').toLowerCase();
                const color = NODE_COLORS[typeKey] || NODE_COLORS.default;
                return (
                    <div className="absolute pointer-events-none rounded-xl p-3 border text-xs space-y-1 backdrop-blur-sm"
                        style={{
                            left: Math.min(node.x + 15, dimensions.width - 220),
                            top: Math.max(10, node.y - 30),
                            background: 'rgba(10,15,25,0.9)',
                            borderColor: `${color}40`,
                            boxShadow: `0 0 20px ${color}15`,
                            zIndex: 10,
                        }}>
                        <p className="font-bold text-white">{node.name || node.id}</p>
                        <p className="text-slate-400">Type: <span className="capitalize" style={{color}}>{node.type || '—'}</span></p>
                        <p className="text-slate-400">Risk: <span className="font-mono font-bold" style={{ color: RISK[riskLevel(node.risk_score || 0)]?.color }}>
                            {typeof node.risk_score === 'number' ? (node.risk_score * 100).toFixed(0) + '%' : '—'}
                        </span></p>
                    </div>
                );
            })()}

            {/* Legend */}
            <div className="absolute bottom-3 left-3 flex gap-3 text-xs text-slate-500 bg-black/30 backdrop-blur-sm rounded-lg px-3 py-2 border" style={{borderColor:'rgba(255,255,255,0.05)'}}>
                {Object.entries(NODE_COLORS).filter(([k]) => k !== 'default').map(([type, color]) => (
                    <div key={type} className="flex items-center gap-1.5">
                        <div className="w-2 h-2 rounded-full" style={{ background: color, boxShadow:`0 0 6px ${color}` }} />
                        <span className="capitalize">{type}</span>
                    </div>
                ))}
                <div className="flex items-center gap-1.5 ml-2">
                    <div className="w-4 h-0.5 rounded" style={{background:'#ef4444',boxShadow:'0 0 6px #ef4444'}} />
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
                        const risk = pathRiskLevel(p.total_risk_score || p.risk_score || 0);
                        const isExpanded = expanded === i;
                        const pathNodes = p.nodes || p.path || [];
                        const desc = pathDescription(p);
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
                                        <td colSpan="4" className="px-8 py-5 bg-white/[0.01] border-t" style={{ borderColor: 'rgba(255,255,255,0.04)' }}>
                                            <div className="space-y-4">
                                                <div className="flex flex-col gap-2">
                                                    <p className="text-xs text-slate-500 uppercase tracking-wider">Threat Description</p>
                                                    <p className="text-sm text-slate-300 leading-relaxed max-w-2xl">{desc}</p>
                                                </div>
                                                <div className="flex flex-col gap-3">
                                                    <p className="text-xs text-slate-500 uppercase tracking-wider">Attack Chain</p>
                                                    <div className="flex items-center gap-2 overflow-x-auto pb-2 no-scrollbar">
                                                        {pathNodes.map((n, j) => {
                                                            const nodeName = typeof n === 'string' ? n : (n.name || n.id || 'Unknown');
                                                            const nodeType = (typeof n === 'object' ? n.label || n.type || '' : '').toLowerCase();
                                                            const color = NODE_COLORS[nodeType] || NODE_COLORS.default;
                                                            return (
                                                                <React.Fragment key={j}>
                                                                    <div className="flex items-center gap-2 px-3 py-2 rounded-xl border shrink-0"
                                                                        style={{ borderColor: `${color}30`, background: `${color}08` }}>
                                                                        <div className="p-1 rounded-md" style={{ background: `${color}20` }}>
                                                                            <Circle className="h-3 w-3" style={{ color }} />
                                                                        </div>
                                                                        <div className="flex flex-col">
                                                                            <span className="text-[10px] text-slate-500 leading-none mb-0.5">{typeof n === 'object' ? n.label || 'Node' : 'Node'}</span>
                                                                            <span className="text-xs font-mono text-slate-200">{nodeName}</span>
                                                                        </div>
                                                                    </div>
                                                                    {j < pathNodes.length - 1 && (
                                                                        <div className="flex flex-col items-center shrink-0">
                                                                            <Minus className="h-4 w-8 text-slate-700" />
                                                                        </div>
                                                                    )}
                                                                </React.Fragment>
                                                            );
                                                        })}
                                                    </div>
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
    const { demoMode } = useContext(SettingsContext);
    const [view, setView] = useState('graph');
    const [summary, setSummary] = useState({ total_nodes: 0, total_edges: 0, high_risk_nodes: 0, attack_paths_found: 0 });
    const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
    const [paths, setPaths] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [usingDemo, setUsingDemo] = useState(false);

    const applyDemoData = useCallback(() => {
        setGraphData(DEMO_GRAPH);
        setPaths(DEMO_PATHS);
        setSummary(DEMO_SUMMARY);
        setUsingDemo(true);
        setError(null);
    }, []);

    const fetchAll = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [summaryRes, graphRes, pathsRes] = await Promise.allSettled([
                fetch(`${GRAPH_API}/summary`),
                fetch(`${GRAPH_API}/data`),
                fetch(`${GRAPH_API}/paths`),
            ]);

            let nextGraph = { nodes: [], edges: [] };
            let nextPaths = [];
            let nextSummary = { total_nodes: 0, total_edges: 0, suspicious_edges: 0, top_risky: [] };
            let liveData = false;

            if (summaryRes.status === 'fulfilled' && summaryRes.value.ok) {
                const s = await summaryRes.value.json();
                const nc = s.node_counts || {};
                const ec = s.edge_counts || {};
                nextSummary = {
                    total_nodes: Object.values(nc).reduce((a, b) => a + b, 0),
                    total_edges: Object.values(ec).reduce((a, b) => a + b, 0),
                    suspicious_edges: ec.SUSPICIOUS_CONNECTION || 0,
                    top_risky: s.top_risky_entities || [],
                };
                liveData = nextSummary.total_nodes > 0;
            }
            if (graphRes.status === 'fulfilled' && graphRes.value.ok) {
                nextGraph = await graphRes.value.json();
                if (nextGraph.nodes?.length) liveData = true;
            }
            if (pathsRes.status === 'fulfilled' && pathsRes.value.ok) {
                const body = await pathsRes.value.json();
                nextPaths = Array.isArray(body) ? body : body.paths || [];
            }

            const graphEmpty = !nextGraph.nodes?.length;
            const pathsEmpty = !nextPaths.length;

            if (graphEmpty || (demoMode && pathsEmpty)) {
                applyDemoData();
                if (!graphEmpty) {
                    setGraphData(nextGraph);
                    setSummary(nextSummary);
                    setUsingDemo(pathsEmpty);
                }
                return;
            }

            setUsingDemo(false);
            setSummary(nextSummary);
            setGraphData(nextGraph);
            setPaths(pathsEmpty ? DEMO_PATHS : nextPaths);
        } catch (err) {
            applyDemoData();
            setError(`Graph service unreachable (${err.message}). Showing demo data.`);
        } finally {
            setLoading(false);
        }
    }, [applyDemoData, demoMode]);

    useEffect(() => {
        fetchAll();
        const interval = setInterval(fetchAll, 10000);
        return () => clearInterval(interval);
    }, [fetchAll]);

    // Sidebar: top risky entities
    const riskyNodes = useMemo(() => {
        if (!graphData.nodes) return [];
        return [...graphData.nodes]
            .map(n => ({
                ...n,
                type: (n.type || n.label || 'default').toLowerCase(),
                displayName: n.name || n.label || n.id || 'Unknown'
            }))
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
                    { label: 'Total Edges', value: summary.total_edges || graphData.edges?.length || 0, color: '#a78bfa', icon: <Minus className="h-5 w-5" /> },
                    { label: 'Suspicious Links', value: summary.suspicious_edges || 0, color: '#ef4444', icon: <AlertTriangle className="h-5 w-5" /> },
                    { label: 'Attack Paths', value: (Array.isArray(paths) ? paths : paths.paths || []).length, color: '#f59e0b', icon: <GitBranch className="h-5 w-5" /> },
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

            {usingDemo && (
                <div className="rounded-xl p-3 text-sm border flex items-center justify-between gap-3"
                    style={{ background: 'rgba(16,185,129,0.06)', borderColor: 'rgba(16,185,129,0.25)', color: '#6ee7b7' }}>
                    <span>
                        Showing demo attack graph — run{' '}
                        <code className="text-emerald-300">python3 scripts/inject_demo_alerts.py</code>{' '}
                        after the graph service starts for live Kafka-fed data.
                    </span>
                </div>
            )}

            {error && !usingDemo && (
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
                                            <p className="text-xs font-mono text-slate-200 truncate">{node.displayName}</p>
                                            <p className="text-[10px] text-slate-500 capitalize">{node.type}</p>
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
