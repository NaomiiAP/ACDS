import React, { useState, useEffect, useCallback } from 'react';
import {
  Shield, CheckCircle, XCircle, Clock, Zap, FileCode,
  RefreshCw, AlertTriangle, RotateCcw, Lock,
} from 'lucide-react';
import { POLICY_API } from '../config/api';
import { DEMO_POLICY_RULES } from '../data/demoPolicyRules';

const CARD_BG = '#0c1018';
const CARD_BORDER = 'rgba(255,255,255,0.06)';

const STATUS_STYLE = {
  pending: { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', icon: Clock },
  approved: { color: '#3b82f6', bg: 'rgba(59,130,246,0.12)', icon: CheckCircle },
  executed: { color: '#10b981', bg: 'rgba(16,185,129,0.12)', icon: Zap },
  rejected: { color: '#ef4444', bg: 'rgba(239,68,68,0.12)', icon: XCircle },
  failed: { color: '#ef4444', bg: 'rgba(239,68,68,0.12)', icon: AlertTriangle },
  rolled_back: { color: '#94a3b8', bg: 'rgba(148,163,184,0.12)', icon: RotateCcw },
};

const ACTION_LABELS = {
  block_ip: 'Block IP',
  isolate_process: 'Isolate Process',
  throttle: 'Throttle',
  alert_only: 'Advisory',
};

function StatusBadge({ status }) {
  const s = STATUS_STYLE[status] || STATUS_STYLE.pending;
  const Icon = s.icon;
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold capitalize"
      style={{ background: s.bg, color: s.color, border: `1px solid ${s.color}40` }}>
      <Icon className="h-3 w-3" />
      {status}
    </span>
  );
}

export default function Policy() {
  const [actions, setActions] = useState([]);
  const [rules, setRules] = useState([]);
  const [settings, setSettings] = useState({});
  const [summary, setSummary] = useState({});
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('rules');
  const [filter, setFilter] = useState('all');
  const [fetchError, setFetchError] = useState(null);
  const [usingDemoRules, setUsingDemoRules] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const [actionsRes, rulesRes, summaryRes] = await Promise.all([
        fetch(`${POLICY_API}/actions?limit=100`),
        fetch(`${POLICY_API}/rules`),
        fetch(`${POLICY_API}/summary`),
      ]);

      let gotData = false;

      if (actionsRes.ok) {
        const data = await actionsRes.json();
        setActions(data.actions || []);
        gotData = true;
      }
      if (rulesRes.ok) {
        const data = await rulesRes.json();
        setRules(data.rules || []);
        setSettings(data.settings || {});
        setUsingDemoRules(false);
        gotData = true;
      } else {
        setRules(DEMO_POLICY_RULES);
        setUsingDemoRules(true);
      }
      if (summaryRes.ok) {
        const summaryData = await summaryRes.json();
        setSummary(summaryData);
        gotData = true;
      }

      if (!gotData) {
        setFetchError('Policy engine not reachable on port 8200. Start: python3 acds/policy_service/policy_main.py');
        setRules(DEMO_POLICY_RULES);
        setUsingDemoRules(true);
      }
    } catch (e) {
      console.error('Policy fetch error:', e);
      setFetchError(`Cannot reach policy service: ${e.message}`);
      setRules(DEMO_POLICY_RULES);
      setUsingDemoRules(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 8000);

    let ws;
    try {
      const policyBase = POLICY_API.replace('/api/policy', '');
      const policyWs = policyBase.startsWith('http')
        ? `${policyBase.replace(/^http/, 'ws')}/ws/policy`
        : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/policy`;
      ws = new WebSocket(policyWs);
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === 'policy_action' && msg.data) {
            setActions(prev => {
              const aid = msg.data.action_id;
              const next = prev.filter(a => a.action_id !== aid);
              return [msg.data, ...next];
            });
          }
        } catch { /* ignore */ }
      };
    } catch { /* ws optional */ }

    return () => {
      clearInterval(interval);
      if (ws) ws.close();
    };
  }, [fetchAll]);

  const handleApprove = async (actionId) => {
    await fetch(`${POLICY_API}/actions/${actionId}/approve`, { method: 'POST' });
    setTimeout(fetchAll, 500);
  };

  const handleReject = async (actionId) => {
    await fetch(`${POLICY_API}/actions/${actionId}/reject?reason=Rejected%20by%20analyst`, { method: 'POST' });
    setTimeout(fetchAll, 500);
  };

  const handleRollback = async (actionId) => {
    await fetch(`${POLICY_API}/actions/${actionId}/rollback`, { method: 'POST' });
    setTimeout(fetchAll, 500);
  };

  const filtered = filter === 'all'
    ? actions
    : actions.filter(a => a.status === filter);

  const pendingCount = summary.pending_approvals ?? actions.filter(a => a.status === 'pending').length;

  return (
    <div className="p-6 space-y-5" style={{ background: '#0a0d12', minHeight: 'calc(100vh - 64px)' }}>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Shield className="h-5 w-5 text-blue-400" />
            Response &amp; Policy Engine
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">
            YAML-based rules · Auto isolation · Human-in-the-loop approval
          </p>
        </div>
        <button onClick={fetchAll}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border text-slate-400 hover:text-white"
          style={{ borderColor: CARD_BORDER, background: 'rgba(255,255,255,0.03)' }}>
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'YAML Rules', value: rules.filter(r => r.enabled !== false).length, color: '#3b82f6', icon: FileCode },
          { label: 'Pending Approval', value: pendingCount, color: '#f59e0b', icon: Clock },
          { label: 'Executed', value: summary.executed ?? actions.filter(a => a.status === 'executed').length, color: '#10b981', icon: Zap },
          { label: 'Dry Run', value: settings.dry_run !== false ? 'ON' : 'OFF', color: '#a78bfa', icon: Lock },
        ].map(c => (
          <div key={c.label} className="rounded-2xl p-5 border" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs text-slate-500 uppercase tracking-wider">{c.label}</p>
              <div className="w-8 h-8 rounded-lg flex items-center justify-center"
                style={{ background: `${c.color}18`, color: c.color }}>
                <c.icon className="h-4 w-4" />
              </div>
            </div>
            <p className="text-3xl font-bold" style={{ color: c.color }}>{c.value}</p>
          </div>
        ))}
      </div>

      {fetchError && (
        <div className="rounded-xl p-3 text-sm border"
          style={{ background: 'rgba(239,68,68,0.06)', borderColor: 'rgba(239,68,68,0.25)', color: '#fca5a5' }}>
          {fetchError}
        </div>
      )}

      {usingDemoRules && !fetchError && (
        <div className="rounded-xl p-3 text-sm border"
          style={{ background: 'rgba(245,158,11,0.06)', borderColor: 'rgba(245,158,11,0.25)', color: '#fcd34d' }}>
          Showing cached rule definitions — connect to the policy engine on port 8200 for live actions.
        </div>
      )}

      {settings.dry_run !== false && !fetchError && (
        <div className="rounded-xl p-3 text-sm border"
          style={{ background: 'rgba(59,130,246,0.06)', borderColor: 'rgba(59,130,246,0.25)', color: '#93c5fd' }}>
          Dry-run mode is active — actions are logged to audit.log but not enforced via iptables.
          Set <code className="text-blue-300">ENFORCE=true</code> on the policy service for live blocking.
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2">
        {[
          { key: 'actions', label: `Actions${pendingCount ? ` (${pendingCount} pending)` : ''}` },
          { key: 'rules', label: 'YAML Rules' },
        ].map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-1.5 rounded-full text-xs font-medium border transition-all ${tab === t.key ? 'text-blue-400' : 'text-slate-500 hover:text-white'}`}
            style={{
              borderColor: tab === t.key ? 'rgba(59,130,246,0.3)' : CARD_BORDER,
              background: tab === t.key ? 'rgba(59,130,246,0.08)' : 'transparent',
            }}>
            {t.label}
          </button>
        ))}
        {tab === 'actions' && (
          <div className="ml-auto flex gap-1">
            {['all', 'pending', 'executed', 'rejected'].map(f => (
              <button key={f} onClick={() => setFilter(f)}
                className={`px-3 py-1 rounded-full text-xs capitalize ${filter === f ? 'text-white bg-white/10' : 'text-slate-500'}`}>
                {f}
              </button>
            ))}
          </div>
        )}
      </div>

      {tab === 'actions' ? (
        <div className="rounded-2xl border overflow-hidden" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
          {filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-slate-600 gap-3">
              <Shield className="h-12 w-12" />
              <p>No policy actions yet</p>
              <p className="text-sm">Start the policy engine, then run <code className="text-cyan-400">python3 scripts/inject_demo_alerts.py</code></p>
              <p className="text-xs text-slate-500">Policy service: <code className="text-cyan-400">python3 acds/policy_service/policy_main.py</code></p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-slate-500 uppercase tracking-wider border-b"
                  style={{ borderColor: CARD_BORDER, background: 'rgba(255,255,255,0.02)' }}>
                  <th className="px-5 py-3 text-left">Rule / Action</th>
                  <th className="px-5 py-3 text-left">Target</th>
                  <th className="px-5 py-3 text-left">Alert</th>
                  <th className="px-5 py-3 text-left">Status</th>
                  <th className="px-5 py-3 text-right">Controls</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(a => {
                  const sum = a.alert_summary || {};
                  return (
                    <tr key={a.action_id} className="border-t hover:bg-white/[0.02]"
                      style={{ borderColor: 'rgba(255,255,255,0.04)' }}>
                      <td className="px-5 py-4">
                        <p className="font-mono text-slate-200 text-xs">{a.rule_id}</p>
                        <p className="text-xs text-slate-500 mt-0.5">{ACTION_LABELS[a.action] || a.action}</p>
                        {a.auto_execute && (
                          <span className="text-[10px] text-emerald-500">auto</span>
                        )}
                        {a.human_override_required && (
                          <span className="text-[10px] text-amber-500 ml-1">approval required</span>
                        )}
                      </td>
                      <td className="px-5 py-4 font-mono text-xs text-slate-300">{a.target || '—'}</td>
                      <td className="px-5 py-4 text-xs text-slate-400">
                        <span className="text-slate-200">{sum.predicted_label || '—'}</span>
                        {' '}
                        {sum.ensemble_score != null && (
                          <span className="text-amber-400">{(sum.ensemble_score * 100).toFixed(0)}%</span>
                        )}
                        <br />
                        <span className="font-mono">{sum.process_name}</span>
                        {sum.dst_ip && <span> → {sum.dst_ip}</span>}
                      </td>
                      <td className="px-5 py-4">
                        <StatusBadge status={a.status} />
                        {a.result?.message && (
                          <p className="text-[10px] text-slate-500 mt-1 max-w-xs truncate" title={a.result.message}>
                            {a.result.message}
                          </p>
                        )}
                      </td>
                      <td className="px-5 py-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {a.status === 'pending' && (
                            <>
                              <button onClick={() => handleApprove(a.action_id)}
                                className="px-3 py-1 rounded-lg text-xs font-medium text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/10">
                                Approve
                              </button>
                              <button onClick={() => handleReject(a.action_id)}
                                className="px-3 py-1 rounded-lg text-xs font-medium text-red-400 border border-red-500/30 hover:bg-red-500/10">
                                Reject
                              </button>
                            </>
                          )}
                          {a.status === 'executed' && (
                            <button onClick={() => handleRollback(a.action_id)}
                              className="px-3 py-1 rounded-lg text-xs text-slate-400 border border-white/10 hover:bg-white/5">
                              Rollback
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      ) : (
        <div className="grid gap-3">
          {rules.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 text-slate-600 gap-2">
              <FileCode className="h-10 w-10" />
              <p>No rules loaded</p>
            </div>
          )}
          {rules.map(rule => (
            <div key={rule.id} className="rounded-2xl p-5 border"
              style={{ background: CARD_BG, borderColor: rule.enabled === false ? 'rgba(255,255,255,0.03)' : CARD_BORDER, opacity: rule.enabled === false ? 0.5 : 1 }}>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="font-mono text-sm text-blue-300">{rule.id}</p>
                  <p className="text-slate-300 text-sm mt-1">{rule.description}</p>
                </div>
                <div className="flex gap-2 shrink-0">
                  <span className="px-2 py-0.5 rounded text-xs font-bold"
                    style={{ background: 'rgba(59,130,246,0.15)', color: '#60a5fa' }}>
                    {ACTION_LABELS[rule.action] || rule.action}
                  </span>
                  {rule.auto_execute && (
                    <span className="px-2 py-0.5 rounded text-xs text-emerald-400 bg-emerald-500/10">Auto</span>
                  )}
                  {rule.require_approval && (
                    <span className="px-2 py-0.5 rounded text-xs text-amber-400 bg-amber-500/10">Human approval</span>
                  )}
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2 text-xs font-mono text-slate-500">
                {rule.match?.min_ensemble_score != null && (
                  <span className="px-2 py-0.5 rounded bg-white/5">score ≥ {rule.match.min_ensemble_score}</span>
                )}
                {rule.match?.labels?.map(l => (
                  <span key={l} className="px-2 py-0.5 rounded bg-white/5">{l}</span>
                ))}
                {rule.match?.dst_ports?.map(p => (
                  <span key={p} className="px-2 py-0.5 rounded bg-white/5">port {p}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
