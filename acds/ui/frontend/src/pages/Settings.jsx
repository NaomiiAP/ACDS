import React, { useState, useEffect, useContext, useCallback } from 'react';
import { TelemetryContext } from '../context/TelemetryContext';
import { SettingsContext } from '../context/SettingsContext';
import { Wifi, WifiOff, Download, Trash2, CheckCircle, AlertCircle, RefreshCw, Database, Zap, ToggleLeft, ToggleRight } from 'lucide-react';

const CARD_BG = '#111620';
const CARD_BORDER = 'rgba(255,255,255,0.07)';
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/telemetry';

function SectionTitle({ children }) {
    return <h3 className="text-xs text-slate-500 uppercase tracking-widest font-semibold mb-4">{children}</h3>;
}

function SettingsRow({ label, desc, children }) {
    return (
        <div className="flex items-center justify-between py-4 border-b" style={{ borderColor: CARD_BORDER }}>
            <div>
                <p className="text-sm font-medium text-slate-200">{label}</p>
                {desc && <p className="text-xs text-slate-500 mt-0.5">{desc}</p>}
            </div>
            <div className="ml-6 flex-shrink-0">{children}</div>
        </div>
    );
}

function ReadonlyTag({ value }) {
    return (
        <span className="px-3 py-1 rounded-lg font-mono text-xs border text-emerald-400"
            style={{ background: 'rgba(16,185,129,0.07)', borderColor: 'rgba(16,185,129,0.2)' }}>
            {value}
        </span>
    );
}

function Toggle({ on, onToggle }) {
    return (
        <button onClick={onToggle} className="transition-all" title={on ? 'Disable' : 'Enable'}>
            {on
                ? <ToggleRight className="h-7 w-7 text-emerald-400" />
                : <ToggleLeft className="h-7 w-7 text-slate-600" />}
        </button>
    );
}

export default function Settings() {
    const { events, connected, clearBuffer } = useContext(TelemetryContext);
    // Pull from global SettingsContext so changes affect all pages
    const { autoScroll, setAutoScroll, hideNoise, setHideNoise, verboseTs, setVerboseTs, demoMode, setDemoMode } = useContext(SettingsContext);

    const [apiStatus, setApiStatus] = useState(null);
    const [toast, setToast] = useState(null);

    const showToast = useCallback((msg, ok = true) => {
        setToast({ msg, ok });
        setTimeout(() => setToast(null), 3000);
    }, []);

    const fetchStatus = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/api/status`);
            if (res.ok) setApiStatus(await res.json());
        } catch {
            setApiStatus(null);
        }
    }, []);

    useEffect(() => {
        fetchStatus();
        const t = setInterval(fetchStatus, 5000);
        return () => clearInterval(t);
    }, [fetchStatus]);

    const downloadEvents = async (n) => {
        try {
            const res = await fetch(`${API_BASE}/api/events?limit=${n}`);
            const data = await res.json();
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a'); a.href = url;
            a.download = `acds_events_${Date.now()}.json`; a.click();
            URL.revokeObjectURL(url);
            showToast(`Downloaded ${data.length} events`);
        } catch { showToast('Download failed', false); }
    };

    const downloadStats = async () => {
        try {
            const res = await fetch(`${API_BASE}/api/stats`);
            const data = await res.json();
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url; a.download = `acds_stats_${Date.now()}.json`; a.click();
            URL.revokeObjectURL(url); showToast('Stats snapshot downloaded');
        } catch { showToast('Download failed', false); }
    };

    const handleClearBuffer = () => {
        clearBuffer();
        showToast('Local event buffer cleared');
    };

    return (
        <div className="p-6 max-w-3xl mx-auto space-y-8 relative" style={{ background: '#0a0d12', minHeight: 'calc(100vh - 64px)' }}>

            {/* Toast */}
            {toast && (
                <div className="fixed top-4 right-4 z-50 flex items-center gap-2 px-4 py-3 rounded-xl text-sm font-medium shadow-xl"
                    style={{
                        background: toast.ok ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
                        border: `1px solid ${toast.ok ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
                        color: toast.ok ? '#34d399' : '#f87171'
                    }}>
                    {toast.ok ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
                    {toast.msg}
                </div>
            )}

            <div>
                <h2 className="text-xl font-bold text-white">Settings</h2>
                <p className="text-sm text-slate-500 mt-1">Configure the ACDS Telemetry UI behaviour and connections</p>
            </div>

            {/* ── Connection Health ── */}
            <div className="rounded-2xl p-6 border" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
                <div className="flex items-center justify-between mb-5">
                    <SectionTitle>Connection Health</SectionTitle>
                    <button onClick={fetchStatus} className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors">
                        <RefreshCw className="h-3 w-3" /> Refresh
                    </button>
                </div>
                <div className="grid grid-cols-3 gap-4">
                    {[
                        { label: 'WebSocket', ok: connected, hint: connected ? 'Streaming live' : 'Reconnecting…' },
                        { label: 'Kafka Bridge', ok: apiStatus?.kafka_connected, hint: apiStatus?.kafka_connected ? 'Consuming events' : 'Not connected' },
                        {
                            label: 'Agent Heartbeat', ok: apiStatus && (Date.now() / 1000 - (apiStatus.last_event_ts || 0)) < 30,
                            hint: apiStatus?.total_events ? `${apiStatus.total_events.toLocaleString()} total` : 'No events yet'
                        },
                    ].map(item => (
                        <div key={item.label} className="flex flex-col items-center gap-2 p-4 rounded-xl border text-center"
                            style={{ background: '#0a0d12', borderColor: item.ok ? 'rgba(16,185,129,0.25)' : 'rgba(239,68,68,0.2)' }}>
                            {item.ok ? <Wifi className="h-5 w-5 text-emerald-400" /> : <WifiOff className="h-5 w-5 text-red-400" />}
                            <span className="text-xs font-semibold" style={{ color: item.ok ? '#34d399' : '#f87171' }}>{item.label}</span>
                            <span className="text-xs text-slate-500">{item.hint}</span>
                        </div>
                    ))}
                </div>
            </div>

            {/* ── Backend Configuration ── */}
            <div className="rounded-2xl p-6 border" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
                <SectionTitle>Backend Configuration</SectionTitle>
                <div className="divide-y" style={{ borderColor: CARD_BORDER }}>
                    <SettingsRow label="WebSocket URL" desc="Real-time event stream endpoint"><ReadonlyTag value={WS_URL} /></SettingsRow>
                    <SettingsRow label="REST API URL" desc="Stats and events REST endpoint"><ReadonlyTag value={API_BASE} /></SettingsRow>
                    <SettingsRow label="Kafka Topic" desc="Source Kafka topic consumed by backend"><ReadonlyTag value="telemetry.raw" /></SettingsRow>
                    <SettingsRow label="Schema Version" desc="Telemetry JSON schema version"><ReadonlyTag value="v1.0" /></SettingsRow>
                </div>
            </div>

            {/* ── UI Behaviour ── */}
            <div className="rounded-2xl p-6 border" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
                <SectionTitle>UI Behaviour</SectionTitle>
                <p className="text-xs text-slate-600 mb-4">These settings are saved to your browser and apply across all pages immediately.</p>
                <div className="divide-y" style={{ borderColor: CARD_BORDER }}>
                    <SettingsRow label="Auto-scroll in Live Stream" desc={autoScroll ? '✅ Live Stream will follow newest events' : '⏸ Scroll position is locked'}>
                        <Toggle on={autoScroll} onToggle={() => { setAutoScroll(!autoScroll); showToast(`Auto-scroll ${!autoScroll ? 'enabled' : 'disabled'}`); }} />
                    </SettingsRow>
                    <SettingsRow label="Hide Noisy Processes" desc={hideNoise ? '✅ init, bash, systemd are hidden in all tables' : 'All processes shown'}>
                        <Toggle on={hideNoise} onToggle={() => { setHideNoise(!hideNoise); showToast(`Noise filter ${!hideNoise ? 'enabled' : 'disabled'}`); }} />
                    </SettingsRow>
                    <SettingsRow label="Verbose Kernel Timestamps" desc={verboseTs ? '✅ Showing full timestamps in Live Stream' : 'Compact HH:mm:ss format'}>
                        <Toggle on={verboseTs} onToggle={() => { setVerboseTs(!verboseTs); showToast(`Verbose timestamps ${!verboseTs ? 'enabled' : 'disabled'}`); }} />
                    </SettingsRow>
                </div>
            </div>

            {/* ── Demo Mode ── */}
            <div className="rounded-2xl p-6 border" style={{ background: CARD_BG, borderColor: demoMode ? 'rgba(16,185,129,0.3)' : CARD_BORDER }}>
                <SectionTitle>Demo Mode</SectionTitle>
                <div className="flex items-center justify-between">
                    <div>
                        <p className="text-sm font-medium text-slate-200">Enable Demo Replay Mode</p>
                        <p className="text-xs text-slate-500 mt-0.5">
                            {demoMode
                                ? '✅ Demo mode active — simulated events are injected at a controlled rate'
                                : 'Replays a sample dataset at a controlled rate. Useful if traffic is low for a demo.'}
                        </p>
                    </div>
                    <div className="flex items-center gap-3">
                        {demoMode && (
                            <span className="px-2 py-0.5 rounded-full text-xs animate-pulse"
                                style={{ background: 'rgba(16,185,129,0.15)', color: '#34d399', border: '1px solid rgba(16,185,129,0.3)' }}>
                                Active
                            </span>
                        )}
                        <Toggle on={demoMode} onToggle={() => { setDemoMode(!demoMode); showToast(demoMode ? 'Demo mode disabled' : 'Demo mode enabled — simulated events active'); }} />
                    </div>
                </div>
            </div>

            {/* ── Buffer & Export ── */}
            <div className="rounded-2xl p-6 border" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
                <SectionTitle>Buffer & Export</SectionTitle>
                <div className="flex items-center gap-2 mb-5 text-sm text-slate-400">
                    <Database className="h-4 w-4 text-emerald-400" />
                    Local buffer: <span className="text-emerald-400 font-mono font-bold">{events.length.toLocaleString()}</span> events (max 10,000)
                </div>
                <div className="flex flex-wrap gap-3">
                    <button onClick={() => downloadEvents(1000)}
                        className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border transition-all hover:bg-white/5"
                        style={{ borderColor: CARD_BORDER, color: '#94a3b8' }}>
                        <Download className="h-4 w-4 text-emerald-400" /> Last 1,000 Events (JSON)
                    </button>
                    <button onClick={() => downloadEvents(100)}
                        className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border transition-all hover:bg-white/5"
                        style={{ borderColor: CARD_BORDER, color: '#94a3b8' }}>
                        <Download className="h-4 w-4 text-teal-400" /> Last 100 Events (JSON)
                    </button>
                    <button onClick={downloadStats}
                        className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border transition-all hover:bg-white/5"
                        style={{ borderColor: CARD_BORDER, color: '#94a3b8' }}>
                        <Zap className="h-4 w-4 text-lime-400" /> Stats Snapshot (JSON)
                    </button>
                    <button onClick={handleClearBuffer}
                        className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border transition-all hover:bg-white/5"
                        style={{ borderColor: 'rgba(239,68,68,0.3)', color: '#f87171' }}>
                        <Trash2 className="h-4 w-4" /> Clear Local Buffer
                    </button>
                </div>
            </div>
        </div>
    );
}
