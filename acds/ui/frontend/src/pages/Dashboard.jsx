import React, { useContext, useState, useMemo } from 'react';
import {
    AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
    Tooltip, ResponsiveContainer, PieChart, Pie, Cell
} from 'recharts';
import { Activity, Server, Shield, LayoutGrid, TrendingUp } from 'lucide-react';
import { TelemetryContext } from '../context/TelemetryContext';

const CARD_BG = '#111620';
const CARD_BORDER = 'rgba(255,255,255,0.07)';

function StatCard({ title, value, sub, icon: Icon, accent }) {
    return (
        <div
            className="rounded-2xl p-5 flex flex-col gap-3 border"
            style={{ background: CARD_BG, borderColor: CARD_BORDER }}
        >
            <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">{title}</span>
                <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: `${accent}18`, border: `1px solid ${accent}30` }}>
                    <Icon className="h-4 w-4" style={{ color: accent }} />
                </div>
            </div>
            <div>
                <p className="text-3xl font-bold text-white">{value}</p>
                {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
            </div>
        </div>
    );
}

export default function Dashboard() {
    const { stats, statsHistory: history } = useContext(TelemetryContext);

    const currentStats = stats || {
        events_per_sec: 0, tcp_count: 0, udp_count: 0,
        unique_hosts: 0, unique_containers: 0, top_processes: []
    };

    const [timeWindow, setTimeWindow] = useState('all');
    const displayHistory = useMemo(() => {
        if (!history) return [];
        if (timeWindow === '10s') return history.slice(-5);
        if (timeWindow === '30s') return history.slice(-15);
        if (timeWindow === '1m') return history.slice(-30);
        return history;
    }, [history, timeWindow]);
    const TIME_OPTS = ['10s', '30s', '1m', 'all'];

    const pieData = [
        { name: 'TCP', value: currentStats.tcp_count },
        { name: 'UDP', value: currentStats.udp_count }
    ].filter(d => d.value > 0);
    if (pieData.length === 0) pieData.push({ name: 'None', value: 1 });

    const PIE_COLORS = ['#10b981', '#14b8a6'];

    // Build bar chart data from top processes
    const barData = currentStats.top_processes.map(([name, count]) => ({
        name: name.length > 10 ? name.slice(0, 10) + '…' : name,
        value: count
    }));

    return (
        <div className="p-6 space-y-6" style={{ background: '#0a0d12', minHeight: 'calc(100vh - 64px)' }}>

            {/* === TOP ROW: Big Stat + Area Chart + Pie === */}
            <div className="grid grid-cols-12 gap-5">

                {/* ---- Large Stat + Area Chart (col-span 8) ---- */}
                <div className="col-span-12 lg:col-span-8 rounded-2xl p-6 border" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
                    {/* Top row inside card */}
                    <div className="flex items-start justify-between mb-6">
                        <div>
                            <p className="text-xs text-slate-500 uppercase tracking-wider font-medium mb-2">Event Flow Rate</p>
                            <div className="flex items-end gap-3">
                                <p className="text-4xl font-bold text-white">
                                    {currentStats.events_per_sec.toFixed(1)}
                                    <span className="text-lg text-slate-500 ml-1">/ s</span>
                                </p>
                                <span className="mb-1 px-2 py-0.5 rounded-full text-xs font-medium"
                                    style={{ background: 'rgba(16,185,129,0.15)', color: '#34d399', border: '1px solid rgba(16,185,129,0.3)' }}>
                                    Live
                                </span>
                            </div>
                        </div>
                        <div className="flex items-center gap-2 p-1 rounded-full border text-xs"
                            style={{ borderColor: CARD_BORDER, background: '#0a0d12' }}>
                            {TIME_OPTS.map(t => (
                                <button key={t} onClick={() => setTimeWindow(t)}
                                    className={`px-3 py-1 rounded-full font-medium transition-colors cursor-pointer ${timeWindow === t ? 'text-emerald-400' : 'text-slate-400 hover:text-white'
                                        }`}
                                    style={timeWindow === t ? { background: 'rgba(16,185,129,0.15)' } : {}}>
                                    {t === 'all' ? 'All' : t}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Area Chart */}
                    <div className="h-52">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={displayHistory} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
                                <defs>
                                    <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="0%" stopColor="#10b981" stopOpacity={0.35} />
                                        <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                                <XAxis dataKey="time" stroke="#334155" fontSize={10} tickMargin={8} minTickGap={30} tick={{ fill: '#475569' }} />
                                <YAxis stroke="#334155" fontSize={10} tick={{ fill: '#475569' }} tickFormatter={v => Math.floor(v)} />
                                <Tooltip
                                    contentStyle={{ background: '#151b28', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '10px', color: '#f1f5f9', fontSize: 12 }}
                                    itemStyle={{ color: '#34d399' }}
                                    labelStyle={{ color: '#94a3b8' }}
                                />
                                <Area type="monotone" dataKey="eps" name="Events/s" stroke="#34d399" strokeWidth={2} fill="url(#areaGrad)" isAnimationActive={false} dot={false} />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* ---- Protocol Distribution Pie (col-span 4) ---- */}
                <div className="col-span-12 lg:col-span-4 rounded-2xl p-6 border flex flex-col" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
                    <p className="text-xs text-slate-500 uppercase tracking-wider font-medium mb-4">Protocol Distribution</p>
                    <div className="flex-1 h-44">
                        <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                                <Pie data={pieData} cx="50%" cy="50%" innerRadius={55} outerRadius={75}
                                    paddingAngle={4} dataKey="value" stroke="none" isAnimationActive={false}>
                                    {pieData.map((entry, i) => (
                                        <Cell key={i} fill={entry.name === 'None' ? '#1e293b' : PIE_COLORS[i % PIE_COLORS.length]} />
                                    ))}
                                </Pie>
                                <Tooltip contentStyle={{ background: '#151b28', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '10px', color: '#f1f5f9', fontSize: 12 }} />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>
                    <div className="flex justify-center gap-6 mt-3 text-xs">
                        <div className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span><span className="text-slate-400">TCP <span className="text-white font-semibold">{currentStats.tcp_count}</span></span></div>
                        <div className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-teal-500"></span><span className="text-slate-400">UDP <span className="text-white font-semibold">{currentStats.udp_count}</span></span></div>
                    </div>
                </div>
            </div>

            {/* === MIDDLE ROW: 4 Stat Cards === */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
                <StatCard title="Events / sec" value={currentStats.events_per_sec.toFixed(1)} sub="Moving 10s average" icon={Activity} accent="#10b981" />
                <StatCard title="Unique Hosts" value={currentStats.unique_hosts} sub="Active endpoints" icon={Server} accent="#14b8a6" />
                <StatCard title="Containers" value={currentStats.unique_containers} sub="Active containers" icon={LayoutGrid} accent="#22c55e" />
                <StatCard title="TCP (10s)" value={currentStats.tcp_count} sub={`UDP: ${currentStats.udp_count}`} icon={Shield} accent="#84cc16" />
            </div>

            {/* === BOTTOM ROW: Top Processes Bar Chart + Process Table === */}
            <div className="grid grid-cols-12 gap-5">

                {/* Bar Chart (col-span 5) */}
                <div className="col-span-12 lg:col-span-5 rounded-2xl p-6 border" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
                    <div className="flex items-center justify-between mb-5">
                        <p className="text-xs text-slate-500 uppercase tracking-wider font-medium">Active Processes</p>
                        <TrendingUp className="h-4 w-4 text-emerald-400" />
                    </div>
                    <div className="h-44">
                        {barData.length > 0 ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={barData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }} barCategoryGap="35%">
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={true} vertical={false} />
                                    <XAxis dataKey="name" stroke="#334155" fontSize={10} tick={{ fill: '#475569' }} />
                                    <YAxis stroke="#334155" fontSize={10} tick={{ fill: '#475569' }} tickFormatter={v => Math.floor(v)} />
                                    <Tooltip contentStyle={{ background: '#151b28', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '10px', color: '#f1f5f9', fontSize: 12 }}
                                        itemStyle={{ color: '#34d399' }} />
                                    <Bar dataKey="value" name="Events" radius={[4, 4, 0, 0]}>
                                        {barData.map((_, i) => (
                                            <Cell key={i} fill={i === 0 ? '#10b981' : i === 1 ? '#14b8a6' : '#1a2d3a'} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        ) : (
                            <div className="h-full flex items-center justify-center text-slate-600 text-sm">No process data</div>
                        )}
                    </div>
                </div>

                {/* Process Table (col-span 7) */}
                <div className="col-span-12 lg:col-span-7 rounded-2xl border overflow-hidden" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
                    <div className="px-6 py-4 border-b flex items-center justify-between" style={{ borderColor: CARD_BORDER }}>
                        <p className="text-xs text-slate-500 uppercase tracking-wider font-medium">Top Processes</p>
                        <span className="text-xs text-slate-600">Last 10 seconds</span>
                    </div>
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="text-xs text-slate-600 uppercase tracking-wider" style={{ background: 'rgba(255,255,255,0.02)' }}>
                                <th className="px-6 py-3 text-left font-medium">Process</th>
                                <th className="px-6 py-3 text-right font-medium">Events</th>
                                <th className="px-6 py-3 font-medium">Share</th>
                            </tr>
                        </thead>
                        <tbody>
                            {currentStats.top_processes.length === 0 ? (
                                <tr>
                                    <td colSpan="3" className="px-6 py-10 text-center text-slate-600 text-sm">
                                        No active processes detected
                                    </td>
                                </tr>
                            ) : (
                                currentStats.top_processes.map(([name, count], i) => {
                                    const total = currentStats.top_processes.reduce((a, c) => a + c[1], 0);
                                    const pct = total > 0 ? (count / total) * 100 : 0;
                                    return (
                                        <tr key={i} className="border-t hover:bg-white/[0.02] transition-colors" style={{ borderColor: CARD_BORDER }}>
                                            <td className="px-6 py-3">
                                                <span className="px-2 py-0.5 rounded text-xs font-mono border text-slate-300"
                                                    style={{ background: 'rgba(255,255,255,0.05)', borderColor: CARD_BORDER }}>
                                                    {name}
                                                </span>
                                            </td>
                                            <td className="px-6 py-3 text-right font-mono text-slate-300">{count.toLocaleString()}</td>
                                            <td className="px-6 py-3">
                                                <div className="flex items-center gap-2">
                                                    <div className="flex-1 h-1.5 rounded-full" style={{ background: 'rgba(255,255,255,0.07)' }}>
                                                        <div className="h-1.5 rounded-full transition-all duration-500"
                                                            style={{ width: `${pct}%`, background: i === 0 ? '#10b981' : i === 1 ? '#14b8a6' : '#1e3a30' }} />
                                                    </div>
                                                    <span className="text-xs text-slate-500 w-8 text-right">{pct.toFixed(0)}%</span>
                                                </div>
                                            </td>
                                        </tr>
                                    );
                                })
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
