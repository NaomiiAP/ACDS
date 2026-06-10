import { useEffect, useRef, useState, useCallback } from 'react';
import { API_BASE, wsUrl } from '../config/api';

const ML_WS = wsUrl('/ws/ml-alerts');

export function useMLAlerts(maxEvents = 500) {
    const [connected, setConnected] = useState(false);
    const [alerts, setAlerts] = useState([]);
    const [isPaused, setIsPaused] = useState(false);
    const [stats, setStats] = useState({
        total_alerts: 0,
        high_severity: 0,
        anomalies_detected: 0,
        avg_ensemble_score: 0,
    });

    const wsRef = useRef(null);
    const isPausedRef = useRef(isPaused);

    useEffect(() => {
        isPausedRef.current = isPaused;
    }, [isPaused]);

    // WebSocket connection
    useEffect(() => {
        let reconnectTimeout;

        function connect() {
            const ws = new WebSocket(ML_WS);

            ws.onopen = () => {
                setConnected(true);
                console.log("ML Alerts WebSocket connected");
            };

            ws.onmessage = (e) => {
                if (isPausedRef.current) return;

                try {
                    const msg = JSON.parse(e.data);
                    if (msg.type === 'ml_alert' || msg.type === 'alert') {
                        setAlerts(prev => {
                            const next = [msg.data, ...prev];
                            return next.slice(0, maxEvents);
                        });
                    }
                } catch (err) {
                    console.error("Failed parsing ML WS message", err);
                }
            };

            ws.onclose = () => {
                setConnected(false);
                wsRef.current = null;
                console.log("ML Alerts WebSocket closed. Reconnecting in 3s...");
                reconnectTimeout = setTimeout(connect, 3000);
            };

            ws.onerror = (err) => {
                console.error("ML Alerts WebSocket error", err);
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

    // Poll stats every 3 seconds
    useEffect(() => {
        const fetchStats = async () => {
            try {
                const res = await fetch(`${API_BASE}/api/ml/stats`);
                if (res.ok) {
                    const data = await res.json();
                    setStats(data);
                }
            } catch (err) {
                console.error("Failed to fetch ML stats", err);
            }
        };

        fetchStats();
        const interval = setInterval(fetchStats, 3000);
        return () => clearInterval(interval);
    }, []);

    // Fetch historical alerts via REST on mount (fallback if WebSocket missed them)
    useEffect(() => {
        const fetchAlerts = async () => {
            try {
                const res = await fetch(`${API_BASE}/api/ml/alerts?limit=${maxEvents}`);
                if (res.ok) {
                    const data = await res.json();
                    if (Array.isArray(data) && data.length > 0) {
                        setAlerts(prev => {
                            if (prev.length > 0) return prev; // don't overwrite WS data
                            return data;
                        });
                    }
                }
            } catch (err) {
                console.error("Failed to fetch ML alerts", err);
            }
        };
        fetchAlerts();
    }, [maxEvents]);

    const clearBuffer = useCallback(() => {
        setAlerts([]);
    }, []);

    return { connected, alerts, stats, isPaused, setIsPaused, clearBuffer };
}
