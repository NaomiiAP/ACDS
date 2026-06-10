import { useEffect, useRef, useState, useCallback } from 'react';
import { API_BASE, wsUrl } from '../config/api';

const WEBSOCKET_URL = wsUrl('/ws/telemetry');

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
    const isPausedRef = useRef(isPaused);

    useEffect(() => {
        isPausedRef.current = isPaused;
    }, [isPaused]);

    // REST fallback — load buffered events even if WebSocket is slow to connect
    useEffect(() => {
        const fetchEvents = async () => {
            try {
                const res = await fetch(`${API_BASE}/api/events?limit=${maxEvents}`);
                if (res.ok) {
                    const data = await res.json();
                    if (Array.isArray(data) && data.length > 0) {
                        setEvents(prev => (prev.length > 0 ? prev : data));
                    }
                }
            } catch (err) {
                console.error('Failed to fetch telemetry events', err);
            }
        };
        fetchEvents();
        const interval = setInterval(fetchEvents, 5000);
        return () => clearInterval(interval);
    }, [maxEvents]);

    useEffect(() => {
        let reconnectTimeout;

        function connect() {
            const ws = new WebSocket(WEBSOCKET_URL);

            ws.onopen = () => {
                setConnected(true);
                console.log('Telemetry WebSocket connected');
            };

            ws.onmessage = (e) => {
                if (isPausedRef.current) return;

                try {
                    const msg = JSON.parse(e.data);
                    if (msg.type === 'event') {
                        setEvents(prev => {
                            const copy = [...prev, msg.data];
                            return copy.slice(-maxEvents);
                        });
                    }
                } catch (err) {
                    console.error('Failed parsing WS message', err);
                }
            };

            ws.onclose = () => {
                setConnected(false);
                wsRef.current = null;
                console.log('Telemetry WebSocket closed. Reconnecting in 3s...');
                reconnectTimeout = setTimeout(connect, 3000);
            };

            ws.onerror = (err) => {
                console.error('Telemetry WebSocket error', err);
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

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const res = await fetch(`${API_BASE}/api/stats?window=10s`);
                if (res.ok) {
                    const data = await res.json();
                    setStats(data);

                    setStatsHistory(prev => {
                        const copy = [...prev, { time: new Date().toLocaleTimeString(), eps: data.events_per_sec }];
                        return copy.slice(-1800);
                    });
                }
            } catch (err) {
                console.error('Failed to fetch global stats', err);
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
