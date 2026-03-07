import React, { useState, useEffect, useRef, useMemo } from 'react';
import { AlertTriangle, ShieldAlert, Shield, Activity, X, ChevronRight } from 'lucide-react';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/telemetry';
const THREAT_WS = WS_URL.replace('/ws/telemetry', '/ws/threats');
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const CARD_BG = '#111620';
const CARD_BORDER = 'rgba(255,255,255,0.07)';

const RISK = {
    high: { color: '#ef4444', bg: 'rgba(239,68,68,0.12)', border: 'rgba(239,68,68,0.3)', label: 'HIGH' },
    medium: { color: '#f59e0b', bg: 'rgba(245,158,11,0.10)', border: 'rgba(245,158,11,0.3)', label: 'MEDIUM' },
    low: { color: '#10b981', bg: 'rgba(16,185,129,0.08)', border: 'rgba(16,185,129,0.2)', label: 'LOW' },
};

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

function ScoreBar({ score }) {
    const pct = Math.round(score * 100);
    const color = score >= 0.6 ? '#ef4444' : score >= 0.3 ? '#f59e0b' : '#10b981';
    return (
        <div className="flex items-center gap-2 min-w-[80px]">
            <div className="flex-1 h-1.5 rounded-full bg-white/5 overflow-hidden">
                <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
            </div>
            <span className="text-xs font-mono w-7 text-right" style={{ color }}>{pct}</span>
        </div>
    );
}

function DetailPanel({ event, onClose }) {
    if (!event) return null;
    const r = RISK[event.risk_level] || RISK.low;
    return (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
            <div className="w-full max-w-2xl rounded-2xl border shadow-2xl overflow-hidden"
                style={{ background: '#0e1117', borderColor: r.border }}>
                {/* Header */}
                <div className="px-6 py-4 flex items-center justify-between border-b" style={{ borderColor: CARD_BORDER, background: r.bg }}>
                    <div className="flex items-center gap-3">
                        <ShieldAlert className="h-5 w-5" style={{ color: r.color }} />
                        <div>
                            <p className="font-bold text-white">{event.process_name || 'unknown'}</p>
                            <p className="text-xs text-slate-400 font-mono">{event.src_ip} → {event.dst_ip}:{event.dst_port}</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <RiskBadge level={event.risk_level} />
                        <button onClick={onClose} className="text-slate-500 hover:text-white transition"><X className="h-5 w-5" /></button>
                    </div>
                </div>
                {/* Content */}
                <div className="p-6 grid grid-cols-2 gap-4 text-sm">
                    {[
                        ['Host', event.host_id || '—'],
                        ['PID', event.pid && event.pid !== -1 ? event.pid : '—'],
                        ['Process', event.process_name || 'unknown'],
                        ['Container', event.container_id || 'bare-metal'],
                        ['Protocol', event.protocol],
                        ['Correlated', event.correlated ? '✅ Yes' : '❌ No (unmatched)'],
                        ['Risk Score', (event.risk_score * 100).toFixed(0) + '%'],
                        ['TLS', event.tls_fingerprint || 'none'],
                        ['Entropy', typeof event.entropy === 'number' ? event.entropy.toFixed(3) : '—'],
                        ['Burst Rate', event.burst_rate],
                        ['Avg Pkt Size', event.avg_packet_size ? event.avg_packet_size.toFixed(0) + ' B' : '—'],
                        ['IAT', event.inter_arrival_time ? event.inter_arrival_time.toFixed(3) + 's' : '—'],
                    ].map(([k, v]) => (
                        <div key={k} className="flex items-center gap-2">
                            <span className="text-slate-500 w-28 shrink-0">{k}</span>
                            <span className="font-mono text-slate-200">{v}</span>
                        </div>
                    ))}
                </div>
                {event.risk_reasons?.length > 0 && (
                    <div className="px-6 pb-5">
                        <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Detection Reasons</p>
                        <div className="flex flex-wrap gap-2">
                            {event.risk_reasons.map(r => (
                                <span key={r} className="px-2 py-0.5 rounded text-xs font-mono"
                                    style={{ background: 'rgba(239,68,68,0.08)', color: '#f87171', border: '1px solid rgba(239,68,68,0.2)' }}>
                                    {r}
                                </span>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

export default function Threats() {
    const [threats, setThreats] = useState([]);
    const [selected, setSelected] = useState(null);
    const [filter, setFilter] = useState('all');
    const [connected, setConnected] = useState(false);
    const wsRef = useRef(null);

    // Stats derived live from the threats array — updates instantly on every WebSocket message
    const stats = useMemo(() => ({
        total: threats.length,
        high: threats.filter(t => t.risk_level === 'high').length,
        medium: threats.filter(t => t.risk_level === 'medium').length,
        low: threats.filter(t => t.risk_level === 'low').length,
    }), [threats]);

    // WebSocket for live threats
    useEffect(() => {
        function connect() {
            const ws = new WebSocket(THREAT_WS);
            ws.onopen = () => { setConnected(true); };
            ws.onclose = () => { setConnected(false); setTimeout(connect, 3000); };
            ws.onerror = () => ws.close();
            ws.onmessage = (e) => {
                try {
                    const msg = JSON.parse(e.data);
                    if (msg.type === 'threat') {
                        setThreats(prev => {
                            const next = [msg.data, ...prev];
                            return next.slice(0, 2000); // cap
                        });
                    }
                } catch { }
            };
            wsRef.current = ws;
        }
        connect();
        return () => wsRef.current?.close();
    }, []);

    const displayed = useMemo(() => {
        if (filter === 'all') return threats;
        return threats.filter(t => t.risk_level === filter);
    }, [threats, filter]);

    return (
        <div className="p-6 space-y-5" style={{ background: '#0a0d12', minHeight: 'calc(100vh - 64px)' }}>

            {selected && <DetailPanel event={selected} onClose={() => setSelected(null)} />}

            {/* Header row */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold text-white flex items-center gap-2">
                        <ShieldAlert className="h-5 w-5 text-red-400" /> Threat Intelligence
                    </h2>
                    <p className="text-sm text-slate-500 mt-0.5">Correlated DPI + Telemetry enriched flows with risk scoring</p>
                </div>
                <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border"
                        style={{
                            borderColor: connected ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)',
                            background: connected ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)',
                            color: connected ? '#34d399' : '#f87171'
                        }}>
                        <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
                        {connected ? 'Live' : 'Disconnected'}
                    </div>
                </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-4 gap-4">
                {[
                    { label: 'Total Flows', value: stats.total, icon: <Activity className="h-5 w-5" />, color: '#64748b' },
                    { label: 'HIGH Risk', value: stats.high, icon: <AlertTriangle className="h-5 w-5" />, color: '#ef4444' },
                    { label: 'MEDIUM Risk', value: stats.medium, icon: <ShieldAlert className="h-5 w-5" />, color: '#f59e0b' },
                    { label: 'LOW Risk', value: stats.low, icon: <Shield className="h-5 w-5" />, color: '#10b981' },
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

            {/* Filter tabs */}
            <div className="flex gap-2">
                {['all', 'high', 'medium', 'low'].map(f => (
                    <button key={f} onClick={() => setFilter(f)}
                        className={`px-4 py-1.5 rounded-full text-xs font-medium border transition-all capitalize ${filter === f ? 'text-emerald-400' : 'text-slate-500 hover:text-white'}`}
                        style={{
                            borderColor: filter === f ? 'rgba(16,185,129,0.3)' : CARD_BORDER,
                            background: filter === f ? 'rgba(16,185,129,0.08)' : 'transparent'
                        }}>
                        {f === 'all' ? `All (${threats.length})` : f}
                    </button>
                ))}
            </div>

            {/* Threat Table */}
            {displayed.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-24 gap-4 text-slate-600">
                    <Shield className="h-12 w-12" />
                    <p className="text-lg font-medium">No threats detected yet</p>
                    <p className="text-sm">Start the DPI service and correlation service to see enriched flows</p>
                </div>
            ) : (
                <div className="rounded-2xl border overflow-hidden" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="text-xs text-slate-500 uppercase tracking-wider border-b"
                                style={{ borderColor: CARD_BORDER, background: 'rgba(255,255,255,0.02)' }}>
                                <th className="px-5 py-3 text-left">Risk</th>
                                <th className="px-5 py-3 text-left">Score</th>
                                <th className="px-5 py-3 text-left">Process</th>
                                <th className="px-5 py-3 text-left">Src → Dst</th>
                                <th className="px-5 py-3 text-right">Entropy</th>
                                <th className="px-5 py-3 text-right">Burst</th>
                                <th className="px-5 py-3 text-left">TLS</th>
                                <th className="px-5 py-3 text-center">Correlated</th>
                                <th className="px-5 py-3 text-right">Time</th>
                                <th className="px-3 py-3"></th>
                            </tr>
                        </thead>
                        <tbody>
                            {displayed.map((t, i) => {
                                const r = RISK[t.risk_level] || RISK.low;
                                return (
                                    <tr key={i}
                                        className="border-t cursor-pointer hover:bg-white/[0.025] transition-colors"
                                        style={{
                                            borderColor: 'rgba(255,255,255,0.04)',
                                            background: t.risk_level === 'high' ? 'rgba(239,68,68,0.03)' : ''
                                        }}
                                        onClick={() => setSelected(t)}>
                                        <td className="px-5 py-3"><RiskBadge level={t.risk_level} /></td>
                                        <td className="px-5 py-3"><ScoreBar score={t.risk_score || 0} /></td>
                                        <td className="px-5 py-3 font-mono font-bold text-slate-200">{t.process_name || 'unknown'}</td>
                                        <td className="px-5 py-3 font-mono text-xs text-slate-400">{t.src_ip} → {t.dst_ip}:{t.dst_port}</td>
                                        <td className="px-5 py-3 text-right font-mono text-slate-300 text-xs">{typeof t.entropy === 'number' ? t.entropy.toFixed(2) : '—'}</td>
                                        <td className="px-5 py-3 text-right font-mono text-slate-300 text-xs">{t.burst_rate ?? '—'}</td>
                                        <td className="px-5 py-3 font-mono text-xs text-slate-400 max-w-[90px] truncate">{t.tls_fingerprint || 'none'}</td>
                                        <td className="px-5 py-3 text-center text-xs">{t.correlated ? '✅' : '❌'}</td>
                                        <td className="px-5 py-3 text-right font-mono text-slate-500 text-xs">
                                            {t.timestamp ? new Date(t.timestamp * 1000).toLocaleTimeString() : '—'}
                                        </td>
                                        <td className="px-3 py-3 text-slate-600"><ChevronRight className="h-4 w-4" /></td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
