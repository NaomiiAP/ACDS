/**
 * API / WebSocket URLs.
 * .env.development.local is auto-written by scripts/write_frontend_env.sh with the WSL IP.
 * Fallback: same-origin (Vite proxy) when env vars are unset.
 */
export const API_BASE = import.meta.env.VITE_API_BASE || ''

/** Attack Graph service (port 8100). Uses Vite proxy /api/graph when unset. */
export const GRAPH_API = import.meta.env.VITE_GRAPH_API
  ? `${import.meta.env.VITE_GRAPH_API.replace(/\/$/, '')}/api/graph`
  : API_BASE
    ? `${API_BASE.replace(':8000', ':8100')}/api/graph`
    : '/api/graph'

export function wsUrl(path) {
  if (import.meta.env.VITE_WS_URL && path === '/ws/telemetry') {
    return import.meta.env.VITE_WS_URL
  }
  if (import.meta.env.VITE_API_BASE) {
    const base = import.meta.env.VITE_API_BASE.replace(/^http/, 'ws')
    return `${base}${path}`
  }
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}${path}`
}
