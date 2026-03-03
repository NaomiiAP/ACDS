import React, { createContext, useContext } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Activity, LayoutDashboard, Server, Settings, TerminalSquare } from 'lucide-react';
import Dashboard from './pages/Dashboard';
import LiveStream from './pages/LiveStream';
import { useTelemetry } from './hooks/useTelemetry';
import { TelemetryContext } from './context/TelemetryContext';

function NavItem({ to, icon: Icon, label }) {
  const location = useLocation();
  const isActive = location.pathname === to;
  return (
    <Link
      to={to}
      className={`flex items-center space-x-3 px-4 py-3 transition ${isActive ? 'bg-slate-700 text-emerald-400 border-l-4 border-emerald-400' : 'hover:bg-slate-700 text-slate-300'}`}
    >
      <Icon className="h-5 w-5" />
      <span className="font-medium">{label}</span>
    </Link>
  );
}

function AppLayout({ children }) {
  const telemetryState = useTelemetry(10000);

  return (
    <TelemetryContext.Provider value={telemetryState}>
      <div className="flex h-screen bg-slate-900 text-slate-100 font-sans overflow-hidden">
        {/* Sidebar */}
        <aside className="w-64 bg-slate-800 border-r border-slate-700 flex flex-col shrink-0">
          <div className="p-5 border-b border-slate-700 flex items-center space-x-3">
            <Activity className="h-6 w-6 text-emerald-400" />
            <span className="font-bold text-xl tracking-wide bg-clip-text text-transparent bg-gradient-to-r from-emerald-400 to-teal-400">
              ACDS Telemetry
            </span>
          </div>
          <nav className="flex-1 py-4 space-y-1 overflow-y-auto">
            <NavItem to="/" icon={LayoutDashboard} label="Dashboard" />
            <NavItem to="/live" icon={TerminalSquare} label="Live Stream" />

            <div className="mt-8 px-4" />

            <div className="flex items-center space-x-3 px-4 py-3 opacity-40 cursor-not-allowed text-slate-400">
              <Server className="h-5 w-5" />
              <span>Hosts</span>
            </div>
            <div className="flex items-center space-x-3 px-4 py-3 opacity-40 cursor-not-allowed text-slate-400">
              <Settings className="h-5 w-5" />
              <span>Settings</span>
            </div>
          </nav>
        </aside>

        {/* Main Content */}
        <main className="flex-1 flex flex-col min-w-0">
          {/* Header */}
          <header className="h-16 bg-slate-800/80 backdrop-blur-md border-b border-slate-700 flex items-center justify-between px-6 shrink-0 z-10">
            <h1 className="text-lg font-semibold text-slate-200">System Monitor</h1>

            <div className="flex items-center space-x-6">
              <div className="flex items-center space-x-2 bg-slate-900 px-3 py-1.5 rounded-full border border-slate-700/50">
                <span className="relative flex h-2.5 w-2.5">
                  {telemetryState.connected && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>}
                  <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${telemetryState.connected ? 'bg-green-500' : 'bg-red-500'}`}></span>
                </span>
                <span className="text-xs font-medium text-slate-300">
                  {telemetryState.connected ? 'WS Connected' : 'WS Disconnected'}
                </span>
              </div>

              <div className="text-xs text-slate-400 px-3 py-1 bg-slate-900 rounded-md border border-slate-800">
                Buffer: <span className="text-emerald-400 font-mono">{telemetryState.events.length.toLocaleString()}</span> items
              </div>
            </div>
          </header>

          {/* Dynamic Page content */}
          <div className="flex-1 overflow-y-auto w-full">
            {children}
          </div>
        </main>
      </div>
    </TelemetryContext.Provider>
  );
}

function App() {
  return (
    <Router>
      <AppLayout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/live" element={<LiveStream />} />
        </Routes>
      </AppLayout>
    </Router>
  );
}

export default App;
