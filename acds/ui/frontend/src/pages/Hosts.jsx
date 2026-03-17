import React, { useMemo, useState, useContext } from 'react';
import { TelemetryContext } from '../context/TelemetryContext';
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell
} from 'recharts';
import { Server, ChevronRight, ArrowLeft, Wifi, WifiOff, Activity, Globe } from 'lucide-react';

const CARD_BG = '#111620';
const CARD_BORDER = 'rgba(255,255,255,0.07)';
const ACCENT = '#10b981';

function StatusBadge({ status }) {
    const map = {
        active: { color: '#10b981', bg: 'rgba(16,185,129,0.12)', label: 'Active' },
        idle: { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', label: 'Idle' },
        offline: { color: '#ef4444', bg: 'rgba(239,68,68,0.12)', label: 'Offline' },
    };
    const s = map[status] || map.offline;
    return (
        <span className="px-2 py-0.5 rounded-full text-xs font-medium flex items-center gap-1.5 w-fit"
            style={{ background: s.bg, color: s.color, border: `1px solid ${s.color}30` }}>
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: s.color }}></span>
            {s.label}
        </span>
    );
}

function computeHostStatus(lastTs) {
    const age = Date.now() / 1000 - lastTs;
    if (age < 5) return 'active';
    if (age < 30) return 'idle';
    return 'offline';
}

export default function Hosts() {
    const { events } = useContext(TelemetryContext);
    const [selected, setSelected] = useState(null);

    // --- Compute host table data from event buffer ---
    const hosts = useMemo(() => {
        const map = {};
        for (const e of events) {
            const hid = e.host_id || 'unknown';
            if (!map[hid]) {
                map[hid] = {
                    host_id: hid, events: [], processes: new Set(), containers: new Set(),
                    tcp: 0, udp: 0, failures: 0, dests: {}
                };
            }
            const h = map[hid];
            h.events.push(e);
            if (e.process_name) h.processes.add(e.process_name);
            if (e.container_id && e.container_id !== '' && e.container_id !== 'host')
                h.containers.add(e.container_id);
            const proto = String(e.protocol || '').toUpperCase();
            if (proto === 'TCP' || proto === '6') h.tcp++;
            else if (proto === 'UDP' || proto === '17') h.udp++;
            if (!e.success) h.failures++;
            if (e.dst_ip) h.dests[e.dst_ip] = (h.dests[e.dst_ip] || 0) + 1;
        }
        return Object.values(map).map(h => {
            const now = Date.now() / 1000;
            const recent10s = h.events.filter(e => now - (e.timestamp || 0) <= 10);
            const lastTs = Math.max(...h.events.map(e => e.timestamp || 0));
            return {
                host_id: h.host_id,
                status: computeHostStatus(lastTs),
                lastSeen: lastTs,
                eventsPerSec: (recent10s.length / 10).toFixed(1),
                totalEvents: h.events.length,
                uniqueProcesses: h.processes.size,
                activeContainers: h.containers.size,
                tcp: h.tcp, udp: h.udp,
                failures: h.failures,
                topDests: Object.entries(h.dests).sort((a, b) => b[1] - a[1]).slice(0, 5),
                topProcesses: [...h.processes].slice(0, 5),
                allEvents: h.events,
            };
        }).sort((a, b) => b.totalEvents - a.totalEvents);
    }, [events]);

    const selectedHost = selected ? hosts.find(h => h.host_id === selected) : null;

    if (selectedHost) {
        return <HostDetail host={selectedHost} onBack={() => setSelected(null)} />;
    }

    return (
        <div className="p-6 space-y-5" style={{ background: '#0a0d12', minHeight: 'calc(100vh - 64px)' }}>
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold text-white">Connected Hosts</h2>
                    <p className="text-sm text-slate-500 mt-1">Machines running the ACDS telemetry agent</p>
                </div>
                <div className="px-3 py-1.5 rounded-full text-sm font-medium"
                    style={{ background: 'rgba(16,185,129,0.1)', color: '#34d399', border: '1px solid rgba(16,185,129,0.2)' }}>
                    {hosts.length} host{hosts.length !== 1 ? 's' : ''}
                </div>
            </div>

            {hosts.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-24 gap-4 text-slate-600">
                    <Server className="h-12 w-12" />
                    <p className="text-lg font-medium">No hosts detected yet</p>
                    <p className="text-sm">Start the telemetry agent to see host data here</p>
                </div>
            ) : (
                <div className="rounded-2xl border overflow-hidden" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="text-xs text-slate-500 uppercase tracking-wider border-b" style={{ borderColor: CARD_BORDER, background: 'rgba(255,255,255,0.02)' }}>
                                <th className="px-6 py-4 text-left font-medium">Host ID</th>
                                <th className="px-6 py-4 text-left font-medium">Status</th>
                                <th className="px-6 py-4 text-right font-medium">Events/sec</th>
                                <th className="px-6 py-4 text-right font-medium">Processes</th>
                                <th className="px-6 py-4 text-right font-medium">Containers</th>
                                <th className="px-6 py-4 text-right font-medium">Total Events</th>
                                <th className="px-6 py-4 text-right font-medium">Last Seen</th>
                                <th className="px-6 py-4 text-center font-medium">Details</th>
                            </tr>
                        </thead>
                        <tbody>
                            {hosts.map((h, i) => (
                                <tr key={h.host_id}
                                    className="border-t hover:bg-white/[0.025] transition-colors cursor-pointer"
                                    style={{ borderColor: CARD_BORDER }}
                                    onClick={() => setSelected(h.host_id)}>
                                    <td className="px-6 py-4">
                                        <div className="flex items-center gap-3">
                                            <div className="w-8 h-8 rounded-lg flex items-center justify-center"
                                                style={{ background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.2)' }}>
                                                <Server className="h-4 w-4 text-emerald-400" />
                                            </div>
                                            <span className="font-mono font-medium text-white">{h.host_id}</span>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4"><StatusBadge status={h.status} /></td>
                                    <td className="px-6 py-4 text-right font-mono text-emerald-400 font-medium">{h.eventsPerSec}</td>
                                    <td className="px-6 py-4 text-right text-slate-300">{h.uniqueProcesses}</td>
                                    <td className="px-6 py-4 text-right text-slate-300">{h.activeContainers}</td>
                                    <td className="px-6 py-4 text-right font-mono text-slate-300">{h.totalEvents.toLocaleString()}</td>
                                    <td className="px-6 py-4 text-right text-slate-500 text-xs font-mono">
                                        {h.lastSeen > 0 ? new Date(h.lastSeen * 1000).toLocaleTimeString() : '—'}
                                    </td>
                                    <td className="px-6 py-4 text-center">
                                        <ChevronRight className="h-4 w-4 text-slate-600 mx-auto group-hover:text-emerald-400 transition-colors" />
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}

function HostDetail({ host, onBack }) {
    const pieData = [
        { name: 'TCP', value: host.tcp },
        { name: 'UDP', value: host.udp }
    ].filter(d => d.value > 0);
    if (pieData.length === 0) pieData.push({ name: 'None', value: 1 });

    // Build mini rate chart from events
    const rateData = useMemo(() => {
        const buckets = {};
        const now = Date.now() / 1000;
        host.allEvents.forEach(e => {
            const t = e.timestamp || 0;
            if (now - t > 120) return; // last 2 minutes
            const bucket = Math.floor(t / 2) * 2;
            buckets[bucket] = (buckets[bucket] || 0) + 1;
        });
        return Object.entries(buckets)
            .sort((a, b) => a[0] - b[0])
            .map(([ts, count]) => ({
                time: new Date(ts * 1000).toLocaleTimeString(),
                eps: count / 2
            }));
    }, [host]);

    const failureRatio = host.totalEvents > 0
        ? ((host.failures / host.totalEvents) * 100).toFixed(1)
        : '0.0';

    return (
        <div className="p-6 space-y-5" style={{ background: '#0a0d12', minHeight: 'calc(100vh - 64px)' }}>
            {/* Back + Title */}
            <div className="flex items-center gap-4">
                <button onClick={onBack} className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-all border text-sm" style={{ borderColor: CARD_BORDER }}>
                    <ArrowLeft className="h-4 w-4" /> Back to Hosts
                </button>
                <div>
                    <h2 className="text-xl font-bold text-white font-mono">{host.host_id}</h2>
                    <StatusBadge status={host.status} />
                </div>
            </div>

            {/* Metrics Row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {[
                    { label: 'Total Events', value: host.totalEvents.toLocaleString(), color: '#10b981' },
                    { label: 'Events / sec', value: host.eventsPerSec, color: '#14b8a6' },
                    { label: 'Failure Rate', value: `${failureRatio}%`, color: '#f59e0b' },
                    { label: 'Processes', value: host.uniqueProcesses, color: '#84cc16' },
                ].map(m => (
                    <div key={m.label} className="rounded-xl p-4 border" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
                        <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">{m.label}</p>
                        <p className="text-2xl font-bold" style={{ color: m.color }}>{m.value}</p>
                    </div>
                ))}
            </div>

            {/* Event Rate Chart + Protocol Pie */}
            <div className="grid grid-cols-12 gap-5">
                <div className="col-span-12 lg:col-span-8 rounded-2xl p-5 border" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
                    <p className="text-xs text-slate-500 uppercase tracking-wider font-medium mb-4">Event Rate (last 2 min)</p>
                    <div className="h-40">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={rateData} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
                                <defs>
                                    <linearGradient id="hostGrad" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="0%" stopColor="#10b981" stopOpacity={0.3} />
                                        <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                                <XAxis dataKey="time" stroke="#334155" fontSize={10} tick={{ fill: '#475569' }} minTickGap={30} />
                                <YAxis stroke="#334155" fontSize={10} tick={{ fill: '#475569' }} />
                                <Tooltip contentStyle={{ background: '#151b28', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '10px', fontSize: 12 }} itemStyle={{ color: '#34d399' }} />
                                <Area type="monotone" dataKey="eps" stroke="#34d399" strokeWidth={2} fill="url(#hostGrad)" isAnimationActive={false} dot={false} />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                <div className="col-span-12 lg:col-span-4 rounded-2xl p-5 border flex flex-col" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
                    <p className="text-xs text-slate-500 uppercase tracking-wider font-medium mb-3">Protocol Split</p>
                    <div className="flex-1 h-36">
                        <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                                <Pie data={pieData} cx="50%" cy="50%" innerRadius={40} outerRadius={55} paddingAngle={3} dataKey="value" stroke="none" isAnimationActive={false}>
                                    {pieData.map((_, i) => <Cell key={i} fill={['#10b981', '#14b8a6', '#1e293b'][i] || '#1e293b'} />)}
                                </Pie>
                                <Tooltip contentStyle={{ background: '#151b28', borderRadius: '10px', fontSize: 12 }} />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>
                    <div className="flex justify-center gap-4 text-xs mt-2">
                        <span className="flex items-center gap-1.5 text-slate-400"><span className="w-2 h-2 rounded-full bg-emerald-500"></span>TCP {host.tcp}</span>
                        <span className="flex items-center gap-1.5 text-slate-400"><span className="w-2 h-2 rounded-full bg-teal-500"></span>UDP {host.udp}</span>
                    </div>
                </div>
            </div>

            {/* Network Summary + Top Processes */}
            <div className="grid grid-cols-2 gap-5">
                {/* Top Destination IPs */}
                <div className="rounded-2xl border overflow-hidden" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
                    <div className="px-5 py-4 border-b flex items-center gap-2" style={{ borderColor: CARD_BORDER }}>
                        <Globe className="h-4 w-4 text-emerald-400" />
                        <p className="text-xs text-slate-400 uppercase tracking-wider font-medium">Top Destination IPs</p>
                    </div>
                    <div className="divide-y" style={{ borderColor: CARD_BORDER }}>
                        {host.topDests.length === 0 ? (
                            <p className="px-5 py-4 text-slate-600 text-sm">No destination data</p>
                        ) : host.topDests.map(([ip, count]) => (
                            <div key={ip} className="px-5 py-3 flex items-center justify-between hover:bg-white/[0.02] transition">
                                <span className="font-mono text-sm text-slate-300">{ip}</span>
                                <span className="text-emerald-400 font-medium text-sm">{count}</span>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Top Processes */}
                <div className="rounded-2xl border overflow-hidden" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
                    <div className="px-5 py-4 border-b flex items-center gap-2" style={{ borderColor: CARD_BORDER }}>
                        <Activity className="h-4 w-4 text-emerald-400" />
                        <p className="text-xs text-slate-400 uppercase tracking-wider font-medium">Top Processes</p>
                    </div>
                    <div className="divide-y" style={{ borderColor: CARD_BORDER }}>
                        {host.topProcesses.length === 0 ? (
                            <p className="px-5 py-4 text-slate-600 text-sm">No process data</p>
                        ) : host.topProcesses.map(proc => (
                            <div key={proc} className="px-5 py-3 hover:bg-white/[0.02] transition">
                                <span className="font-mono text-sm text-slate-300 px-2 py-0.5 rounded border"
                                    style={{ background: 'rgba(16,185,129,0.07)', borderColor: 'rgba(16,185,129,0.2)', color: '#6ee7b7' }}>
                                    {proc}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Filtered Live Stream */}
            <div className="rounded-2xl border" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
                <div className="px-5 py-4 border-b" style={{ borderColor: CARD_BORDER }}>
                    <p className="text-xs text-slate-400 uppercase tracking-wider font-medium">
                        Host Live Stream — <span className="text-emerald-400 font-mono">{host.host_id}</span>
                    </p>
                </div>
                <div className="overflow-x-auto max-h-64 overflow-y-auto">
                    <table className="w-full text-xs font-mono">
                        <thead className="sticky top-0" style={{ background: '#111620' }}>
                            <tr className="text-slate-500 border-b" style={{ borderColor: CARD_BORDER }}>
                                <th className="px-4 py-2 text-left">Time</th>
                                <th className="px-4 py-2 text-left">PID</th>
                                <th className="px-4 py-2 text-left">Process</th>
                                <th className="px-4 py-2 text-left">Proto</th>
                                <th className="px-4 py-2 text-left">Dst IP</th>
                                <th className="px-4 py-2 text-center">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {host.allEvents.slice(-50).reverse().map((e, i) => (
                                <tr key={i} className="border-t hover:bg-white/[0.02]" style={{ borderColor: 'rgba(255,255,255,0.04)' }}>
                                    <td className="px-4 py-2 text-slate-500">{new Date((e.timestamp || 0) * 1000).toLocaleTimeString()}</td>
                                    <td className="px-4 py-2 text-emerald-400">{e.pid}</td>
                                    <td className="px-4 py-2 text-slate-200 font-bold">{e.process_name}</td>
                                    <td className="px-4 py-2 text-teal-400">{e.protocol}</td>
                                    <td className="px-4 py-2 text-green-300">{e.dst_ip}</td>
                                    <td className="px-4 py-2 text-center">
                                        {e.success
                                            ? <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block"></span>
                                            : <span className="w-1.5 h-1.5 rounded-full bg-red-400 inline-block"></span>}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
