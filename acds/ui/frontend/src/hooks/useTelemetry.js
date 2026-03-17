import { useEffect, useRef, useState, useCallback } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const WEBSOCKET_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/telemetry';

export function useTelemetry(maxEvents = 10000) {
    const [connected, setConnected] = useState(false);
    const [events, setEvents] = useState([]);
    const [isPaused, setIsPaused] = useState(false);
    const [stats, setStats] = useState({
        events_per_sec: 0,
        tcp_count: 0,
        udp_count: 0,
        unique_hosts: 0,
        unique_containers: 0,
        top_processes: []
    });
    const [statsHistory, setStatsHistory] = useState([]);

    const wsRef = useRef(null);

    // Use a ref for the isPaused state to avoid reconnecting the websocket on UI toggle
    const isPausedRef = useRef(isPaused);

    useEffect(() => {
        isPausedRef.current = isPaused;
    }, [isPaused]);

    useEffect(() => {
        let reconnectTimeout;

        function connect() {
            const ws = new WebSocket(WEBSOCKET_URL);

            ws.onopen = () => {
                setConnected(true);
                console.log("Telemetry WebSocket connected");
            };

            ws.onmessage = (e) => {
                if (isPausedRef.current) return;

                try {
                    const msg = JSON.parse(e.data);
                    if (msg.type === 'event') {
                        setEvents(prev => {
                            const copy = [...prev, msg.data];
                            return copy.slice(-maxEvents); // keep bounded
                        });
                    }
                } catch (err) {
                    console.error("Failed parsing WS message", err);
                }
            };

            ws.onclose = () => {
                setConnected(false);
                wsRef.current = null;
                console.log("Telemetry WebSocket closed. Reconnecting in 3s...");
                reconnectTimeout = setTimeout(connect, 3000);
            };

            ws.onerror = (err) => {
                console.error("Telemetry WebSocket error", err);
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

    // Fetch Stats Globally
    useEffect(() => {
        const fetchStats = async () => {
            try {
                const res = await fetch(`${API_BASE}/api/stats?window=10s`);
                if (res.ok) {
                    const data = await res.json();
                    setStats(data);

                    setStatsHistory(prev => {
                        const copy = [...prev, { time: new Date().toLocaleTimeString(), eps: data.events_per_sec }];
                        return copy.slice(-1800); // Keep up to 1800 points (~1 hour at 2s intervals) for "All" view
                    });
                }
            } catch (err) {
                console.error("Failed to fetch global stats", err);
            }
        };

        fetchStats();
        const interval = setInterval(fetchStats, 2000);
        return () => clearInterval(interval);
    }, []);

    const clearBuffer = useCallback(() => {
        setEvents([]);
    }, []);

    return { connected, events, isPaused, setIsPaused, clearBuffer, stats, statsHistory };
}
