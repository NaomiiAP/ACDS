import React, { useState, useEffect, useContext } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { Activity, LayoutGrid, Shield, Server } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const COLORS = ['#10b981', '#14b8a6', '#84cc16', '#22c55e', '#0ea5e9'];

function StatCard({ title, value, icon: Icon, colorClass }) {
    return (
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between">
                <div>
                    <p className="text-slate-400 text-sm font-medium mb-1">{title}</p>
                    <h3 className="text-2xl font-bold text-slate-100">{value}</h3>
                </div>
                <div className={`p-3 rounded-lg ${colorClass}`}>
                    <Icon className="h-6 w-6" />
                </div>
            </div>
        </div>
    );
}

import { TelemetryContext } from '../context/TelemetryContext';

export default function Dashboard() {
    const { stats, statsHistory: history } = useContext(TelemetryContext);

    // Provide default fallbacks just in case context hasn't hydrated yet
    const currentStats = stats || {
        events_per_sec: 0,
        tcp_count: 0,
        udp_count: 0,
        unique_hosts: 0,
        unique_containers: 0,
        top_processes: []
    };

    const pieData = [
        { name: 'TCP', value: currentStats.tcp_count },
        { name: 'UDP', value: currentStats.udp_count }
    ].filter(d => d.value > 0);

    // if no data yet, show a grey empty slice
    if (pieData.length === 0) pieData.push({ name: 'None', value: 1 });

    return (
        <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <StatCard title="Events / sec" value={currentStats.events_per_sec.toFixed(1)} icon={Activity} colorClass="bg-emerald-500/10 text-emerald-400" />
                <StatCard title="Unique Hosts" value={currentStats.unique_hosts} icon={Server} colorClass="bg-teal-500/10 text-teal-400" />
                <StatCard title="Active Containers" value={currentStats.unique_containers} icon={LayoutGrid} colorClass="bg-green-500/10 text-green-400" />
                <StatCard title="TCP Conns (10s)" value={currentStats.tcp_count} icon={Shield} colorClass="bg-lime-500/10 text-lime-400" />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2 bg-slate-800 border border-slate-700 rounded-xl p-5 shadow-sm">
                    <h3 className="text-base font-semibold text-slate-200 mb-4">Event Flow Rate</h3>
                    <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={history} margin={{ top: 5, right: 0, left: 0, bottom: 0 }}>
                                <defs>
                                    <linearGradient id="colorEps" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                                <XAxis dataKey="time" stroke="#94a3b8" fontSize={12} tickMargin={10} minTickGap={30} />
                                <YAxis stroke="#94a3b8" fontSize={12} tickFormatter={(val) => Math.floor(val)} />
                                <Tooltip
                                    contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#f8fafc' }}
                                    itemStyle={{ color: '#34d399' }}
                                />
                                <Area type="monotone" dataKey="eps" name="Events/s" stroke="#34d399" strokeWidth={2} fillOpacity={1} fill="url(#colorEps)" isAnimationActive={false} />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 shadow-sm flex flex-col items-center">
                    <h3 className="text-base font-semibold text-slate-200 mb-4 self-start">Protocol Distribution</h3>
                    <div className="h-48 w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                                <Pie
                                    data={pieData}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={60}
                                    outerRadius={80}
                                    paddingAngle={5}
                                    dataKey="value"
                                    stroke="none"
                                    isAnimationActive={false}
                                >
                                    {pieData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.name === 'None' ? '#334155' : COLORS[index % COLORS.length]} />
                                    ))}
                                </Pie>
                                <Tooltip
                                    contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#f8fafc', borderRadius: '0.5rem' }}
                                    itemStyle={{ color: '#f8fafc' }}
                                />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>
                    <div className="flex gap-4 mt-4 text-sm">
                        <div className="flex items-center"><span className="w-3 h-3 rounded-full bg-emerald-500 mr-2"></span><span className="text-slate-300">TCP ({currentStats.tcp_count})</span></div>
                        <div className="flex items-center"><span className="w-3 h-3 rounded-full bg-teal-500 mr-2"></span><span className="text-slate-300">UDP ({currentStats.udp_count})</span></div>
                    </div>
                </div>
            </div>

            <div className="bg-slate-800 border border-slate-700 rounded-xl shadow-sm overflow-hidden">
                <div className="px-6 py-5 border-b border-slate-700">
                    <h3 className="text-base font-semibold text-slate-200">Top Processes</h3>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm whitespace-nowrap">
                        <thead className="bg-slate-900/50 text-slate-400">
                            <tr>
                                <th className="px-6 py-3 font-medium">Process Name</th>
                                <th className="px-6 py-3 font-medium text-right">Events (Last 10s)</th>
                                <th className="px-6 py-3 font-medium">Activity Share</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-700/50">
                            {currentStats.top_processes.length === 0 ? (
                                <tr>
                                    <td colSpan="3" className="px-6 py-8 text-center text-slate-500">No active processes detected</td>
                                </tr>
                            ) : (
                                currentStats.top_processes.map((proc, i) => {
                                    const totalEvents = currentStats.top_processes.reduce((acc, curr) => acc + curr[1], 0);
                                    const percentage = totalEvents > 0 ? (proc[1] / totalEvents) * 100 : 0;

                                    return (
                                        <tr key={i} className="hover:bg-slate-700/30 transition">
                                            <td className="px-6 py-3 font-medium text-slate-200">
                                                <span className="px-2 py-1 bg-slate-700 rounded text-xs mr-2 border border-slate-600 font-mono">
                                                    {proc[0]}
                                                </span>
                                            </td>
                                            <td className="px-6 py-3 text-right text-slate-300">{proc[1].toLocaleString()}</td>
                                            <td className="px-6 py-3">
                                                <div className="w-full bg-slate-700 rounded-full h-1.5">
                                                    <div className="bg-emerald-500 h-1.5 rounded-full" style={{ width: `${percentage}%` }}></div>
                                                </div>
                                            </td>
                                        </tr>
                                    )
                                })
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
