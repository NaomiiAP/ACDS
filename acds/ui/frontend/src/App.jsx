import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Shield, Bell, Settings as SettingsIcon, X, CheckCircle, AlertCircle } from 'lucide-react';
import Dashboard from './pages/Dashboard';
import LiveStream from './pages/LiveStream';
import Hosts from './pages/Hosts';
import SettingsPage from './pages/Settings';
import Threats from './pages/Threats';
import { useTelemetry } from './hooks/useTelemetry';
import { TelemetryContext } from './context/TelemetryContext';
import { SettingsProvider } from './context/SettingsContext';

const NAV_ITEMS = [
  { to: '/', label: 'Overview' },
  { to: '/live', label: 'Live Stream' },
  { to: '/hosts', label: 'Hosts' },
  { to: '/threats', label: 'Threats' },
  { to: '/settings', label: 'Settings' },
];

function TopNavItem({ to, label }) {
  const location = useLocation();
  const isActive = location.pathname === to;
  return (
    <Link to={to}
      className={`px-5 py-2 rounded-full text-sm font-medium transition-all ${isActive
        ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
        : 'text-slate-400 hover:text-slate-200 border border-transparent'
        }`}
    >
      {label}
    </Link>
  );
}

/* ─── Notification Side Panel ─── */
function NotificationPanel({ telemetry, onClose }) {
  const notifications = [];
  if (!telemetry.connected) notifications.push({ type: 'error', msg: 'WebSocket disconnected — attempting reconnect…' });
  if (telemetry.connected) notifications.push({ type: 'ok', msg: 'WebSocket connected and streaming live events.' });
  if (telemetry.events.length > 0) {
    notifications.push({ type: 'ok', msg: `${telemetry.events.length.toLocaleString()} events buffered in memory.` });
  }
  if (telemetry.events.length === 0) {
    notifications.push({ type: 'warn', msg: 'No events received yet. Is the Telemetry Agent running?' });
  }
  return (
    <div className="fixed top-0 right-0 h-full w-80 z-50 shadow-2xl flex flex-col"
      style={{ background: '#0e1117', borderLeft: '1px solid rgba(255,255,255,0.07)' }}>
      <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: 'rgba(255,255,255,0.07)' }}>
        <div className="flex items-center gap-2">
          <Bell className="h-4 w-4 text-emerald-400" />
          <span className="font-semibold text-sm text-white">Notifications</span>
        </div>
        <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors">
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {notifications.map((n, i) => (
          <div key={i} className="flex items-start gap-3 p-3 rounded-xl text-sm"
            style={{
              background: n.type === 'error' ? 'rgba(239,68,68,0.08)' : n.type === 'warn' ? 'rgba(245,158,11,0.08)' : 'rgba(16,185,129,0.08)',
              border: `1px solid ${n.type === 'error' ? 'rgba(239,68,68,0.2)' : n.type === 'warn' ? 'rgba(245,158,11,0.2)' : 'rgba(16,185,129,0.2)'}`,
            }}>
            {n.type === 'ok'
              ? <CheckCircle className="h-4 w-4 text-emerald-400 mt-0.5 shrink-0" />
              : <AlertCircle className={`h-4 w-4 mt-0.5 shrink-0 ${n.type === 'warn' ? 'text-amber-400' : 'text-red-400'}`} />}
            <span style={{ color: n.type === 'error' ? '#f87171' : n.type === 'warn' ? '#fbbf24' : '#6ee7b7' }}>
              {n.msg}
            </span>
          </div>
        ))}
      </div>
      <div className="px-5 py-3 border-t text-xs text-slate-600" style={{ borderColor: 'rgba(255,255,255,0.07)' }}>
        Last updated: {new Date().toLocaleTimeString()}
      </div>
    </div>
  );
}

/* ─── Settings Quick Panel ─── */
function SettingsQuickPanel({ onClose, onOpenFull }) {
  return (
    <div className="fixed top-0 right-0 h-full w-72 z-50 shadow-2xl flex flex-col"
      style={{ background: '#0e1117', borderLeft: '1px solid rgba(255,255,255,0.07)' }}>
      <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: 'rgba(255,255,255,0.07)' }}>
        <div className="flex items-center gap-2">
          <SettingsIcon className="h-4 w-4 text-emerald-400" />
          <span className="font-semibold text-sm text-white">Quick Settings</span>
        </div>
        <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors">
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="flex-1 p-4 space-y-4">
        <p className="text-xs text-slate-500">Quick-access controls for the most common settings.</p>
        <div className="space-y-3">
          <button onClick={() => { onClose(); onOpenFull(); }}
            className="w-full px-4 py-2.5 rounded-xl text-sm font-medium border text-left transition-all hover:bg-white/5 text-slate-200"
            style={{ borderColor: 'rgba(255,255,255,0.07)' }}>
            ⚙️ Open Full Settings Page
          </button>
          <Link to="/hosts" onClick={onClose}
            className="block w-full px-4 py-2.5 rounded-xl text-sm font-medium border text-left transition-all hover:bg-white/5 text-slate-200"
            style={{ borderColor: 'rgba(255,255,255,0.07)' }}>
            🖥️ View All Hosts
          </Link>
          <Link to="/live" onClick={onClose}
            className="block w-full px-4 py-2.5 rounded-xl text-sm font-medium border text-left transition-all hover:bg-white/5 text-slate-200"
            style={{ borderColor: 'rgba(255,255,255,0.07)' }}>
            🔴 Open Live Stream
          </Link>
        </div>
        <div className="rounded-xl p-3 text-xs" style={{ background: 'rgba(16,185,129,0.07)', border: '1px solid rgba(16,185,129,0.15)' }}>
          <p className="text-emerald-400 font-medium mb-1">Schema Version</p>
          <p className="text-slate-400 font-mono">telemetry.raw — v1.0</p>
        </div>
      </div>
    </div>
  );
}

function AppLayout({ children }) {
  const telemetryState = useTelemetry(10000);
  const [showNotifs, setShowNotifs] = useState(false);
  const [showQuickSettings, setShowQuickSettings] = useState(false);

  const openFullSettings = () => {
    window.location.href = '/settings';
  };

  return (
    <TelemetryContext.Provider value={telemetryState}>
      <div className="min-h-screen font-sans" style={{ background: '#0a0d12' }}>
        {/* Overlay */}
        {(showNotifs || showQuickSettings) && (
          <div className="fixed inset-0 bg-black/40 z-40"
            onClick={() => { setShowNotifs(false); setShowQuickSettings(false); }} />
        )}

        {/* Notification Panel */}
        {showNotifs && <NotificationPanel telemetry={telemetryState} onClose={() => setShowNotifs(false)} />}
        {showQuickSettings && (
          <SettingsQuickPanel
            onClose={() => setShowQuickSettings(false)}
            onOpenFull={openFullSettings}
          />
        )}

        {/* Top Header */}
        <header className="h-16 flex items-center justify-between px-8 border-b border-white/5 sticky top-0 z-30" style={{ background: '#0e1117' }}>
          {/* Logo */}
          <Link to="/" className="flex items-center space-x-3 no-underline">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center">
              <Shield className="h-4 w-4 text-emerald-400" />
            </div>
            <span className="font-bold text-base tracking-wide bg-clip-text text-transparent bg-gradient-to-r from-emerald-400 to-teal-300">
              ACDS Telemetry
            </span>
          </Link>

          {/* Nav Tabs */}
          <nav className="flex items-center space-x-1 bg-white/5 border border-white/8 rounded-full px-2 py-1.5">
            {NAV_ITEMS.map(item => <TopNavItem key={item.to} {...item} />)}
          </nav>

          {/* Right Controls */}
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full border text-xs font-medium"
              style={{
                borderColor: telemetryState.connected ? 'rgba(52,211,153,0.3)' : 'rgba(239,68,68,0.3)',
                background: telemetryState.connected ? 'rgba(52,211,153,0.08)' : 'rgba(239,68,68,0.08)',
                color: telemetryState.connected ? '#34d399' : '#ef4444'
              }}>
              <span className={`w-1.5 h-1.5 rounded-full ${telemetryState.connected ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`}></span>
              {telemetryState.connected ? 'Live' : 'Disconnected'}
            </div>
            <div className="text-xs text-slate-500 font-mono px-2 py-1 rounded bg-white/5 border border-white/8">
              <span className="text-emerald-400">{telemetryState.events.length.toLocaleString()}</span> events
            </div>
            <button
              onClick={() => { setShowNotifs(v => !v); setShowQuickSettings(false); }}
              className={`relative w-8 h-8 rounded-full flex items-center justify-center transition-all border ${showNotifs ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400' : 'bg-white/5 border-white/10 text-slate-400 hover:text-white hover:bg-white/10'}`}
              title="Notifications">
              <Bell className="h-4 w-4" />
              {!telemetryState.connected && (
                <span className="absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full bg-red-500"></span>
              )}
            </button>
            <button
              onClick={() => { setShowQuickSettings(v => !v); setShowNotifs(false); }}
              className={`w-8 h-8 rounded-full flex items-center justify-center transition-all border ${showQuickSettings ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400' : 'bg-white/5 border-white/10 text-slate-400 hover:text-white hover:bg-white/10'}`}
              title="Settings">
              <SettingsIcon className="h-4 w-4" />
            </button>
          </div>
        </header>

        <main>{children}</main>
      </div>
    </TelemetryContext.Provider>
  );
}

function App() {
  return (
    <SettingsProvider>
      <Router>
        <AppLayout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/live" element={<LiveStream />} />
            <Route path="/hosts" element={<Hosts />} />
            <Route path="/threats" element={<Threats />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </AppLayout>
      </Router>
    </SettingsProvider>
  );
}

export default App;
