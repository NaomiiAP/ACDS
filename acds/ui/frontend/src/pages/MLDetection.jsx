import React, { useState, useMemo, useEffect } from 'react';
import { Brain, AlertTriangle, ShieldAlert, Activity, X, ChevronRight, BarChart3, Loader2, Info, TrendingUp } from 'lucide-react';
import { useMLAlerts } from '../hooks/useMLAlerts';

const CARD_BG = '#111620';
const CARD_BORDER = 'rgba(255,255,255,0.07)';
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

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

function ScoreBar({ score, color }) {
    const pct = Math.round((score || 0) * 100);
    const barColor = color || (score >= 0.6 ? '#ef4444' : score >= 0.3 ? '#f59e0b' : '#10b981');
    return (
        <div className="flex items-center gap-2 min-w-[80px]">
            <div className="flex-1 h-1.5 rounded-full bg-white/5 overflow-hidden">
                <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: barColor }} />
            </div>
            <span className="text-xs font-mono w-8 text-right" style={{ color: barColor }}>{pct}%</span>
        </div>
    );
}

function TriagePanel({ alertId }) {
    const [triage, setTriage] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [fetched, setFetched] = useState(false);

    const fetchTriage = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${API_BASE}/api/triage/${alertId}`);
            if (!res.ok) throw new Error(`Status ${res.status}`);
            const data = await res.json();
            setTriage(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
            setFetched(true);
        }
    };

    if (!fetched) {
        return (
            <button onClick={fetchTriage}
                className="mt-4 px-4 py-2 rounded-xl text-sm font-medium border transition-all hover:bg-white/5 text-cyan-400"
                style={{ borderColor: 'rgba(6,182,212,0.3)', background: 'rgba(6,182,212,0.08)' }}>
                <div className="flex items-center gap-2">
                    <Brain className="h-4 w-4" />
                    View LLM Triage
                </div>
            </button>
        );
    }

    if (loading) {
        return (
            <div className="mt-4 flex items-center gap-2 text-slate-400 text-sm">
                <Loader2 className="h-4 w-4 animate-spin" /> Fetching triage analysis...
            </div>
        );
    }

    if (error) {
        return (
            <div className="mt-4 text-sm text-red-400">
                Failed to load triage: {error}
            </div>
        );
    }

    if (!triage) return null;

    return (
        <div className="mt-4 space-y-3">
            <p className="text-xs text-slate-500 uppercase tracking-wider">LLM Triage Analysis</p>
            <div className="rounded-xl p-4 border space-y-3" style={{ background: 'rgba(6,182,212,0.04)', borderColor: 'rgba(6,182,212,0.15)' }}>
                {triage.explanation && (
                    <p className="text-sm text-slate-300">{triage.explanation}</p>
                )}
                <div className="flex flex-wrap gap-2">
                    {triage.attack_stage && (
                        <span className="px-2 py-0.5 rounded-full text-xs font-bold"
                            style={{ background: 'rgba(139,92,246,0.12)', color: '#a78bfa', border: '1px solid rgba(139,92,246,0.3)' }}>
                            Stage: {triage.attack_stage}
                        </span>
                    )}
                    {triage.confidence && (
                        <span className="px-2 py-0.5 rounded-full text-xs font-bold"
                            style={{ background: 'rgba(6,182,212,0.12)', color: '#22d3ee', border: '1px solid rgba(6,182,212,0.3)' }}>
                            Confidence: {triage.confidence}
                        </span>
                    )}
                    {triage.severity && (
                        <span className="px-2 py-0.5 rounded-full text-xs font-bold"
                            style={{
                                background: RISK[triage.severity]?.bg || RISK.low.bg,
                                color: RISK[triage.severity]?.color || RISK.low.color,
                                border: `1px solid ${RISK[triage.severity]?.border || RISK.low.border}`
                            }}>
                            Severity: {triage.severity}
                        </span>
                    )}
                </div>
                {triage.mitigation_steps?.length > 0 && (
                    <div>
                        <p className="text-xs text-slate-500 mb-1.5">Mitigation Steps</p>
                        <ol className="list-decimal list-inside space-y-1">
                            {triage.mitigation_steps.map((step, i) => (
                                <li key={i} className="text-sm text-slate-300">{step}</li>
                            ))}
                        </ol>
                    </div>
                )}
                <div className="flex items-center gap-1.5 text-xs text-slate-600 pt-2 border-t" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
                    <Info className="h-3 w-3" />
                    Advisory Only — LLM-generated analysis, verify before acting.
                </div>
            </div>
        </div>
    );
}

function DetailPanel({ alert, onClose }) {
    if (!alert) return null;
    const r = RISK[alert.risk_level] || RISK.low;

    const scores = [
        { label: 'XGBoost', value: alert.xgboost_score, color: '#3b82f6' },
        { label: 'RandomForest', value: alert.random_forest_score, color: '#8b5cf6' },
        { label: 'Autoencoder', value: alert.autoencoder_score, color: '#f59e0b' },
        { label: 'IsolationForest', value: alert.isolation_forest_score, color: '#10b981' },
    ];

    return (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={onClose}>
            <div className="w-full max-w-3xl max-h-[85vh] rounded-2xl border shadow-2xl overflow-y-auto"
                style={{ background: '#0e1117', borderColor: r.border }}
                onClick={e => e.stopPropagation()}>
                {/* Header */}
                <div className="px-6 py-4 flex items-center justify-between border-b" style={{ borderColor: CARD_BORDER, background: r.bg }}>
                    <div className="flex items-center gap-3">
                        <Brain className="h-5 w-5" style={{ color: r.color }} />
                        <div>
                            <p className="font-bold text-white">{alert.process_name || alert.process || 'unknown'}</p>
                            <p className="text-xs text-slate-400 font-mono">
                                {alert.src_ip || '—'} → {alert.dst_ip || '—'}{alert.dst_port ? `:${alert.dst_port}` : ''}
                            </p>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <RiskBadge level={alert.risk_level} />
                        <button onClick={onClose} className="text-slate-500 hover:text-white transition"><X className="h-5 w-5" /></button>
                    </div>
                </div>

                <div className="p-6 space-y-6">
                    {/* Alert Fields */}
                    <div className="grid grid-cols-2 gap-4 text-sm">
                        {[
                            ['Alert ID', alert.alert_id || alert.id || '—'],
                            ['Risk Level', alert.risk_level || '—'],
                            ['Ensemble Score', typeof alert.ensemble_score === 'number' ? alert.ensemble_score.toFixed(4) : '—'],
                            ['Supervised Label', alert.supervised_label || '—'],
                            ['Anomaly Score', typeof alert.anomaly_score === 'number' ? alert.anomaly_score.toFixed(4) : '—'],
                            ['Process', alert.process_name || alert.process || '—'],
                            ['PID', alert.pid || '—'],
                            ['Host', alert.host_id || alert.host || '—'],
                            ['Container', alert.container_id || '—'],
                            ['Protocol', alert.protocol || '—'],
                            ['Source IP', alert.src_ip || '—'],
                            ['Dest IP', alert.dst_ip || '—'],
                            ['Dest Port', alert.dst_port || '—'],
                            ['Timestamp', alert.timestamp ? new Date(typeof alert.timestamp === 'number' ? alert.timestamp * 1000 : alert.timestamp).toLocaleString() : '—'],
                        ].map(([k, v]) => (
                            <div key={k} className="flex items-center gap-2">
                                <span className="text-slate-500 w-28 shrink-0">{k}</span>
                                <span className="font-mono text-slate-200">{v}</span>
                            </div>
                        ))}
                    </div>

                    {/* Score Breakdown */}
                    <div>
                        <p className="text-xs text-slate-500 uppercase tracking-wider mb-3">Model Score Breakdown</p>
                        <div className="space-y-2.5">
                            {scores.map(s => (
                                <div key={s.label} className="flex items-center gap-3">
                                    <span className="text-xs text-slate-400 w-28 shrink-0">{s.label}</span>
                                    <div className="flex-1 h-2 rounded-full bg-white/5 overflow-hidden">
                                        <div className="h-full rounded-full transition-all"
                                            style={{ width: `${Math.round((s.value || 0) * 100)}%`, background: s.color }} />
                                    </div>
                                    <span className="text-xs font-mono w-12 text-right" style={{ color: s.color }}>
                                        {typeof s.value === 'number' ? s.value.toFixed(3) : '—'}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Detection Reasons */}
                    {alert.detection_reasons?.length > 0 && (
                        <div>
                            <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Detection Reasons</p>
                            <div className="flex flex-wrap gap-2">
                                {alert.detection_reasons.map((reason, i) => (
                                    <span key={i} className="px-2 py-0.5 rounded text-xs font-mono"
                                        style={{ background: 'rgba(239,68,68,0.08)', color: '#f87171', border: '1px solid rgba(239,68,68,0.2)' }}>
                                        {reason}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Triage Section */}
                    <TriagePanel alertId={alert.alert_id || alert.id} />
                </div>
            </div>
        </div>
    );
}

const ML_SERVICE_BASE = 'http://localhost:8200';

function ModelPerformance() {
    const [summary, setSummary] = useState(null);
    const [charts, setCharts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        let cancelled = false;
        async function fetchData() {
            setLoading(true);
            setError(null);
            try {
                const [sumRes, chartRes] = await Promise.all([
                    fetch(`${ML_SERVICE_BASE}/evaluation/summary`),
                    fetch(`${ML_SERVICE_BASE}/evaluation/charts`),
                ]);
                if (!sumRes.ok) throw new Error(`Summary: ${sumRes.status}`);
                if (!chartRes.ok) throw new Error(`Charts: ${chartRes.status}`);
                const sumData = await sumRes.json();
                const chartData = await chartRes.json();
                if (!cancelled) {
                    setSummary(sumData);
                    setCharts(chartData.charts || []);
                }
            } catch (err) {
                if (!cancelled) setError(err.message);
            } finally {
                if (!cancelled) setLoading(false);
            }
        }
        fetchData();
        return () => { cancelled = true; };
    }, []);

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-24 gap-4 text-slate-400">
                <Loader2 className="h-10 w-10 animate-spin" />
                <p className="text-sm">Loading model evaluation results...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex flex-col items-center justify-center py-24 gap-4 text-slate-500">
                <BarChart3 className="h-12 w-12" />
                <p className="text-lg font-medium text-slate-400">Evaluation data unavailable</p>
                <p className="text-sm">Run <code className="text-cyan-400">evaluate.py</code> and ensure the ML service is running on port 8200.</p>
                <p className="text-xs text-red-400 mt-1">{error}</p>
            </div>
        );
    }

    const models = summary?.models || {};
    const ensembleMetrics = models.Ensemble || {};
    const xgbMetrics = models.XGBoost || {};
    const rfMetrics = models.RandomForest || {};

    const metricCards = [
        { label: 'Ensemble Accuracy', value: ensembleMetrics.accuracy, color: '#10b981' },
        { label: 'Ensemble F1', value: ensembleMetrics.f1, color: '#06b6d4' },
        { label: 'Ensemble Precision', value: ensembleMetrics.precision, color: '#3b82f6' },
        { label: 'Ensemble Recall', value: ensembleMetrics.recall, color: '#8b5cf6' },
        { label: 'Ensemble AUC', value: ensembleMetrics.auc, color: '#f59e0b' },
    ];

    const chartSections = [
        { title: 'Confusion Matrix (Ensemble)', file: 'confusion_matrix_ensemble.png' },
        { title: 'ROC Curves', file: 'roc_curves.png' },
        { title: 'Precision-Recall Curves', file: 'precision_recall_curves.png' },
        { title: 'Feature Importance', file: 'feature_importance.png' },
        { title: 'Model Comparison', file: 'model_comparison.png' },
        { title: 'Score Distribution', file: 'score_distribution.png' },
        { title: 'Cross-Validation Scores', file: 'cv_scores.png' },
        { title: 'Detection by Attack Type', file: 'detection_by_type.png' },
        { title: 'Confusion Matrix (XGBoost)', file: 'confusion_matrix_xgb.png' },
        { title: 'Confusion Matrix (RandomForest)', file: 'confusion_matrix_rf.png' },
    ];

    const availableCharts = chartSections.filter(c => charts.includes(c.file));

    return (
        <div className="space-y-5">
            {/* Metric cards */}
            <div className="grid grid-cols-5 gap-4">
                {metricCards.map(c => (
                    <div key={c.label} className="rounded-2xl p-5 border" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
                        <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">{c.label}</p>
                        <p className="text-3xl font-bold" style={{ color: c.color }}>
                            {typeof c.value === 'number' ? c.value.toFixed(4) : '--'}
                        </p>
                    </div>
                ))}
            </div>

            {/* Charts grid */}
            <div className="grid grid-cols-2 gap-5">
                {availableCharts.map(c => (
                    <div key={c.file} className="rounded-2xl border overflow-hidden" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
                        <div className="px-5 py-3 border-b" style={{ borderColor: CARD_BORDER }}>
                            <p className="text-sm font-medium text-slate-300">{c.title}</p>
                        </div>
                        <div className="p-3">
                            <img
                                src={`${ML_SERVICE_BASE}/evaluation/chart/${c.file}`}
                                alt={c.title}
                                className="w-full rounded-lg"
                                loading="lazy"
                            />
                        </div>
                    </div>
                ))}
            </div>

            {/* Generated timestamp */}
            {summary?.generated_at && (
                <p className="text-xs text-slate-600 text-center pt-2">
                    Evaluation generated: {new Date(summary.generated_at).toLocaleString()}
                </p>
            )}
        </div>
    );
}

export default function MLDetection() {
    const { connected, alerts, stats } = useMLAlerts(500);
    const [selected, setSelected] = useState(null);
    const [filter, setFilter] = useState('all');
    const [activeTab, setActiveTab] = useState('alerts');

    const derivedStats = useMemo(() => ({
        total: alerts.length || stats.total_alerts || 0,
        high: alerts.filter(a => a.risk_level === 'high').length || stats.high_severity || 0,
        anomalies: alerts.filter(a => a.anomaly_score > 0.5).length || stats.anomalies_detected || 0,
        avgEnsemble: alerts.length > 0
            ? alerts.reduce((sum, a) => sum + (a.ensemble_score || 0), 0) / alerts.length
            : (stats.avg_ensemble_score || 0),
    }), [alerts, stats]);

    const displayed = useMemo(() => {
        if (filter === 'all') return alerts;
        return alerts.filter(a => a.risk_level === filter);
    }, [alerts, filter]);

    return (
        <div className="p-6 space-y-5" style={{ background: '#0a0d12', minHeight: 'calc(100vh - 64px)' }}>

            {selected && <DetailPanel alert={selected} onClose={() => setSelected(null)} />}

            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold text-white flex items-center gap-2">
                        <Brain className="h-5 w-5 text-cyan-400" /> ML Detection
                    </h2>
                    <p className="text-sm text-slate-500 mt-0.5">Ensemble ML pipeline alerts — XGBoost, RandomForest, Autoencoder, IsolationForest</p>
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

            {/* Stat Cards */}
            <div className="grid grid-cols-4 gap-4">
                {[
                    { label: 'Total ML Alerts', value: derivedStats.total, icon: <Brain className="h-5 w-5" />, color: '#64748b' },
                    { label: 'High Severity', value: derivedStats.high, icon: <AlertTriangle className="h-5 w-5" />, color: '#ef4444' },
                    { label: 'Anomalies Detected', value: derivedStats.anomalies, icon: <BarChart3 className="h-5 w-5" />, color: '#f59e0b' },
                    { label: 'Avg Ensemble Score', value: derivedStats.avgEnsemble.toFixed(3), icon: <Activity className="h-5 w-5" />, color: '#10b981', raw: true },
                ].map(c => (
                    <div key={c.label} className="rounded-2xl p-5 border" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
                        <div className="flex items-center justify-between mb-3">
                            <p className="text-xs text-slate-500 uppercase tracking-wider">{c.label}</p>
                            <div className="w-8 h-8 rounded-lg flex items-center justify-center"
                                style={{ background: `${c.color}18`, color: c.color }}>
                                {c.icon}
                            </div>
                        </div>
                        <p className="text-3xl font-bold" style={{ color: c.color }}>
                            {c.raw ? c.value : typeof c.value === 'number' ? c.value.toLocaleString() : c.value}
                        </p>
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
                        {f === 'all' ? `All (${alerts.length})` : f}
                    </button>
                ))}
            </div>

            {/* Alerts Table */}
            {displayed.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-24 gap-4 text-slate-600">
                    <Brain className="h-12 w-12" />
                    <p className="text-lg font-medium">No ML alerts yet</p>
                    <p className="text-sm">Start the ML pipeline service to see ensemble detection alerts</p>
                </div>
            ) : (
                <div className="rounded-2xl border overflow-hidden" style={{ background: CARD_BG, borderColor: CARD_BORDER }}>
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="text-xs text-slate-500 uppercase tracking-wider border-b"
                                style={{ borderColor: CARD_BORDER, background: 'rgba(255,255,255,0.02)' }}>
                                <th className="px-5 py-3 text-left">Risk</th>
                                <th className="px-5 py-3 text-left">Ensemble Score</th>
                                <th className="px-5 py-3 text-left">Supervised Label</th>
                                <th className="px-5 py-3 text-right">Anomaly Score</th>
                                <th className="px-5 py-3 text-left">Process</th>
                                <th className="px-5 py-3 text-left">Src → Dest</th>
                                <th className="px-5 py-3 text-right">Time</th>
                                <th className="px-3 py-3"></th>
                            </tr>
                        </thead>
                        <tbody>
                            {displayed.map((a, i) => (
                                <tr key={a.alert_id || a.id || i}
                                    className="border-t cursor-pointer hover:bg-white/[0.025] transition-colors"
                                    style={{
                                        borderColor: 'rgba(255,255,255,0.04)',
                                        background: a.risk_level === 'high' ? 'rgba(239,68,68,0.03)' : ''
                                    }}
                                    onClick={() => setSelected(a)}>
                                    <td className="px-5 py-3"><RiskBadge level={a.risk_level || 'low'} /></td>
                                    <td className="px-5 py-3"><ScoreBar score={a.ensemble_score || 0} /></td>
                                    <td className="px-5 py-3 font-mono text-xs text-slate-300">{a.supervised_label || '—'}</td>
                                    <td className="px-5 py-3 text-right font-mono text-xs text-slate-300">
                                        {typeof a.anomaly_score === 'number' ? a.anomaly_score.toFixed(3) : '—'}
                                    </td>
                                    <td className="px-5 py-3 font-mono font-bold text-slate-200">{a.process_name || a.process || 'unknown'}</td>
                                    <td className="px-5 py-3 font-mono text-xs text-slate-400">
                                        {a.src_ip || '—'} → {a.dst_ip || '—'}{a.dst_port ? `:${a.dst_port}` : ''}
                                    </td>
                                    <td className="px-5 py-3 text-right font-mono text-slate-500 text-xs">
                                        {a.timestamp ? new Date(typeof a.timestamp === 'number' ? a.timestamp * 1000 : a.timestamp).toLocaleTimeString() : '—'}
                                    </td>
                                    <td className="px-3 py-3 text-slate-600"><ChevronRight className="h-4 w-4" /></td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
