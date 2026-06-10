/**
 * Demo attack graph data — mirrors scripts/inject_demo_alerts.py scenarios.
 * Shown when the graph service is empty or unreachable so the Attack Graph
 * page always has realistic nodes and paths for demos.
 */

export const DEMO_SUMMARY = {
    total_nodes: 14,
    total_edges: 12,
    suspicious_edges: 8,
    top_risky: [],
};

export const DEMO_GRAPH = {
    nodes: [
        { id: 'DESKTOP-GNIKQ6E', label: 'Host', name: 'DESKTOP-GNIKQ6E', risk_score: 0.85 },
        { id: '31337', label: 'Process', name: 'scanner_bolt', risk_score: 0.88 },
        { id: '6666', label: 'Process', name: 'exfiltrator_prime', risk_score: 0.92 },
        { id: '4444', label: 'Process', name: 'svchost_update', risk_score: 0.78 },
        { id: '9999', label: 'Process', name: 'pivoter_tool', risk_score: 0.84 },
        { id: '7777', label: 'Process', name: 'httpflood', risk_score: 0.95 },
        { id: '5555', label: 'Process', name: 'hydra', risk_score: 0.82 },
        { id: '10.0.0.5', label: 'IP', name: '10.0.0.5', risk_score: 0.72 },
        { id: '185.220.101.42', label: 'IP', name: '185.220.101.42', risk_score: 0.91 },
        { id: '104.21.45.67', label: 'IP', name: '104.21.45.67', risk_score: 0.80 },
        { id: '192.168.1.20', label: 'IP', name: '192.168.1.20', risk_score: 0.76 },
        { id: '203.0.113.50', label: 'IP', name: '203.0.113.50', risk_score: 0.88 },
        { id: '10.0.0.50', label: 'IP', name: '10.0.0.50', risk_score: 0.74 },
        { id: '192.168.1.50', label: 'IP', name: '192.168.1.50', risk_score: 0.65 },
    ],
    edges: [
        { source: 0, target: 1, rel_type: 'RUNS', risk_score: 0.85, ensemble_score: 0.88 },
        { source: 0, target: 2, rel_type: 'RUNS', risk_score: 0.85, ensemble_score: 0.92 },
        { source: 0, target: 3, rel_type: 'RUNS', risk_score: 0.85, ensemble_score: 0.78 },
        { source: 0, target: 4, rel_type: 'RUNS', risk_score: 0.85, ensemble_score: 0.84 },
        { source: 0, target: 5, rel_type: 'RUNS', risk_score: 0.85, ensemble_score: 0.95 },
        { source: 0, target: 6, rel_type: 'RUNS', risk_score: 0.85, ensemble_score: 0.82 },
        { source: 1, target: 7, rel_type: 'SUSPICIOUS_CONNECTION', risk_score: 0.88, ensemble_score: 0.88 },
        { source: 2, target: 8, rel_type: 'SUSPICIOUS_CONNECTION', risk_score: 0.92, ensemble_score: 0.92 },
        { source: 3, target: 9, rel_type: 'SUSPICIOUS_CONNECTION', risk_score: 0.78, ensemble_score: 0.78 },
        { source: 4, target: 10, rel_type: 'SUSPICIOUS_CONNECTION', risk_score: 0.84, ensemble_score: 0.84 },
        { source: 5, target: 11, rel_type: 'SUSPICIOUS_CONNECTION', risk_score: 0.95, ensemble_score: 0.95 },
        { source: 6, target: 12, rel_type: 'SUSPICIOUS_CONNECTION', risk_score: 0.82, ensemble_score: 0.82 },
    ],
};

export const DEMO_PATHS = [
    {
        nodes: [
            { labels: ['Host'], id: 'DESKTOP-GNIKQ6E', name: 'DESKTOP-GNIKQ6E', risk_score: 0.85 },
            { labels: ['Process'], id: '31337', name: 'scanner_bolt', risk_score: 0.88 },
            { labels: ['IP'], id: '10.0.0.5', name: '10.0.0.5', risk_score: 0.72 },
        ],
        edges: [{ type: 'SUSPICIOUS_CONNECTION', ensemble_score: 0.88, predicted_label: 'PortScan' }],
        total_risk_score: 2.45,
        path_length: 2,
        description: 'Port scanning from scanner_bolt (PID 31337) probing internal hosts on ports 22, 80, 443, 3389.',
    },
    {
        nodes: [
            { labels: ['Host'], id: 'DESKTOP-GNIKQ6E', name: 'DESKTOP-GNIKQ6E', risk_score: 0.85 },
            { labels: ['Process'], id: '6666', name: 'exfiltrator_prime', risk_score: 0.92 },
            { labels: ['IP'], id: '185.220.101.42', name: '185.220.101.42', risk_score: 0.91 },
        ],
        edges: [{ type: 'SUSPICIOUS_CONNECTION', ensemble_score: 0.92, predicted_label: 'Exfiltration' }],
        total_risk_score: 2.68,
        path_length: 2,
        description: 'High-entropy outbound traffic from exfiltrator_prime to external IP 185.220.101.42 — likely data exfiltration.',
    },
    {
        nodes: [
            { labels: ['Host'], id: 'DESKTOP-GNIKQ6E', name: 'DESKTOP-GNIKQ6E', risk_score: 0.85 },
            { labels: ['Process'], id: '4444', name: 'svchost_update', risk_score: 0.78 },
            { labels: ['IP'], id: '104.21.45.67', name: '104.21.45.67', risk_score: 0.80 },
        ],
        edges: [{ type: 'SUSPICIOUS_CONNECTION', ensemble_score: 0.78, predicted_label: 'C2' }],
        total_risk_score: 2.43,
        path_length: 2,
        description: 'Periodic beaconing from svchost_update to 104.21.45.67 — consistent with C2 command-and-control.',
    },
    {
        nodes: [
            { labels: ['Host'], id: 'DESKTOP-GNIKQ6E', name: 'DESKTOP-GNIKQ6E', risk_score: 0.85 },
            { labels: ['Process'], id: '9999', name: 'pivoter_tool', risk_score: 0.84 },
            { labels: ['IP'], id: '192.168.1.20', name: '192.168.1.20', risk_score: 0.76 },
        ],
        edges: [{ type: 'SUSPICIOUS_CONNECTION', ensemble_score: 0.84, predicted_label: 'Infiltration' }],
        total_risk_score: 2.45,
        path_length: 2,
        description: 'Lateral movement via pivoter_tool targeting multiple hosts on SSH, SMB, and RDP ports.',
    },
    {
        nodes: [
            { labels: ['Host'], id: 'DESKTOP-GNIKQ6E', name: 'DESKTOP-GNIKQ6E', risk_score: 0.85 },
            { labels: ['Process'], id: '7777', name: 'httpflood', risk_score: 0.95 },
            { labels: ['IP'], id: '203.0.113.50', name: '203.0.113.50', risk_score: 0.88 },
        ],
        edges: [{ type: 'SUSPICIOUS_CONNECTION', ensemble_score: 0.95, predicted_label: 'DDoS' }],
        total_risk_score: 2.68,
        path_length: 2,
        description: 'Burst HTTP flood from httpflood toward 203.0.113.50 — botnet-style DDoS pattern detected.',
    },
    {
        nodes: [
            { labels: ['Host'], id: 'DESKTOP-GNIKQ6E', name: 'DESKTOP-GNIKQ6E', risk_score: 0.85 },
            { labels: ['Process'], id: '5555', name: 'hydra', risk_score: 0.82 },
            { labels: ['IP'], id: '10.0.0.50', name: '10.0.0.50', risk_score: 0.74 },
        ],
        edges: [{ type: 'SUSPICIOUS_CONNECTION', ensemble_score: 0.82, predicted_label: 'BruteForce' }],
        total_risk_score: 2.41,
        path_length: 2,
        description: 'SSH brute-force attempts from hydra against 10.0.0.50 — high connection volume on port 22.',
    },
];
