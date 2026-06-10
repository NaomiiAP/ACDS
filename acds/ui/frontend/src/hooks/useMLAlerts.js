import { useEffect, useRef, useState, useCallback } from 'react';
import { API_BASE, wsUrl } from '../config/api';

const ML_WS = wsUrl('/ws/ml-alerts');

export function useMLAlerts(maxEvents = 500) {
    const [connected, setConnected] = useState(false);
    const [alerts, setAlerts] = useState([]);
    const [isPaused, setIsPaused] = useState(false);
    const [stats, setStats] = useState({
        total_alerts: 0,
        high: 0,
        medium: 0,
        low: 0,
        avg_ensemble_score: 0,
    });

    const wsRef = useRef(null);
    const isPausedRef = useRef(isPaused);

    useEffect(() => {
        isPausedRef.current = isPaused;
    }, [isPaused]);

    // REST polling — primary fallback when WebSocket cannot reach WSL backend from Windows
    useEffect(() => {
        const fetchAlerts = async () => {
            try {
                const res = await fetch(`${API_BASE}/api/ml/alerts?limit=${maxEvents}`);
                if (res.ok) {
                    const data = await res.json();
                    if (Array.isArray(data) && data.length > 0) {
                        setAlerts(data);
                        setConnected(true);
                    }
                }
            } catch (err) {
                console.error('Failed to fetch ML alerts', err);
                setConnected(false);
            }
        };

        const fetchStats = async () => {
            try {
                const res = await fetch(`${API_BASE}/api/ml/stats`);
                if (res.ok) {
                    const data = await res.json();
                    setStats(data);
                    if (data.total_alerts > 0) {
                        setConnected(true);
                    }
                }
            } catch (err) {
                console.error('Failed to fetch ML stats', err);
            }
        };

        fetchAlerts();
        fetchStats();
        const interval = setInterval(() => {
            fetchAlerts();
            fetchStats();
        }, 5000);
        return () => clearInterval(interval);
    }, [maxEvents]);

    // WebSocket for live updates (optional enhancement on top of REST)
    useEffect(() => {
        let reconnectTimeout;

        function connect() {
            const ws = new WebSocket(ML_WS);

            ws.onopen = () => {
                setConnected(true);
            };

            ws.onmessage = (e) => {
                if (isPausedRef.current) return;

                try {
                    const msg = JSON.parse(e.data);
                    if (msg.type === 'ml_alert' || msg.type === 'alert') {
                        setAlerts(prev => {
                            const next = [msg.data, ...prev.filter(a => a.alert_id !== msg.data?.alert_id)];
                            return next.slice(0, maxEvents);
                        });
                    }
                } catch (err) {
                    console.error('Failed parsing ML WS message', err);
                }
            };

            ws.onclose = () => {
                wsRef.current = null;
                reconnectTimeout = setTimeout(connect, 5000);
            };

            ws.onerror = () => {
                ws.close();
            };

            wsRef.current = ws;
        }

        connect();

        return () => {
            clearTimeout(reconnectTimeout);
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, [maxEvents]);

    const clearBuffer = useCallback(() => {
        setAlerts([]);
    }, []);

    return { connected, alerts, stats, isPaused, setIsPaused, clearBuffer };
}
