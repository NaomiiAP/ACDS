Telemetry UI — Full Product Specification & Implementation Guide

For frontend developer(s) — everything needed to build a production demo UI for the ACDS Telemetry layer.

This document is the single-source handoff: it defines UX pages/components, data contracts, API/websocket design, UX interactions, UI behavior, performance constraints, deployment, testing, and acceptance criteria. Implement the frontend to consume the telemetry backend (schema v1.0) and present live, filtered, and explorable telemetry that is useful for an instructor/demo and for later DPI integration.

1. Purpose & Goals (one-liner)

A compact, responsive dashboard that visualizes real-time kernel-level telemetry (process + network events collected by eBPF), enabling live demonstrations and quick forensic inspection by humans — and exportable data for downstream DPI/ML.

Success criteria:

Show live stream of telemetry.raw events (schema v1.0).

Provide filtering, search, and drill-down (event → process/container → flows).

Show aggregate visualizations (protocol distribution, events/sec, top processes).

Support stable live demo under load (backpressure handling, virtualization).

Provide basic operator actions: pause stream, mark/flag event, export.

2. Data contract / canonical event (exact fields)

Telemetry JSON (v1.0) — this is the canonical input the frontend consumes:

{
  "schema_version": "1.0",
  "timestamp": 1700000000,              // integer: epoch seconds
  "kernel_timestamp_ns": 12345678901234,// integer: kernel monotonic ns
  "host_id": "node-01",                 // string
  "pid": 4321,                          // int
  "process_name": "curl",               // string (max 16)
  "syscall": "connect",                 // "connect" | "execve"
  "container_id": "abcd1234",           // string or "" (not present is treated as "")
  // if syscall == "connect":
  "success": true,                      // boolean
  "return_code": 0,                     // integer (signed errno)
  "protocol": "TCP",                    // "TCP" | "UDP" | integer-string fallback
  "dst_port": 443,                      // integer (host order)
  "src_port": 45000,                    // integer
  "dst_ip": "8.8.8.8",                  // string IPv4/IPv6
  "src_ip": "10.0.0.5"                  // string
}

Notes for frontend: treat missing optional keys gracefully (e.g., container_id == "" means host process). Use kernel_timestamp_ns for ordering and high-resolution timelines. Convert return_code to signed 32-bit if backend hasn't already.

3. High-level architecture (frontend <-> backend)
Browser UI (React) <--WebSocket/REST--> Backend API (Telemetry consumer/service)
                      |                             ^
                      |                             |
                      v                             |
                 Kafka cluster ----> telemetry.raw topic
                           (producer = eBPF agent)

Backend responsibilities (already available / to be implemented by backend team or you must request from backend devs):

Consume telemetry.raw (Kafka).

Provide a WebSocket endpoint /ws/telemetry that pushes parsed/validated events in real time.

Provide REST endpoints (below) for searching historical events, stats, and basic controls.

Optional: provide a replay endpoint to stream prerecorded events for demo.

4. Recommended tech stack (frontend)

Framework: React 18 (or Next.js if SSR needed later).

State: React Query / SWR for REST, local state for filters; Redux optional.

UI: Tailwind CSS (fast), Headless UI components (modal, dropdown)

Charts: Recharts or Chart.js for simple charts (time-series, pie). Use Recharts by default.

Virtualized list: react-window or react-virtualized for live table.

WebSocket lib: native WebSocket or socket.io (if backend uses socket.io).

Build & deploy: Docker + Nginx; CI: GitHub Actions.

5. Pages & UI components (detailed)
Overview (single-page app with side navigation)

Header — app title, host selection dropdown, status badges (Kafka connection, Agent status), timestamp, user menu.

Left Sidebar — navigation: Dashboard, Live Stream, Hosts, Containers, Processes, Settings.

Main Content — area changes per view.

Page: Dashboard (landing)

Purpose: high-level system state & aggregated telemetry.

Components:

Top row (KPIs):

Events/sec (1m, 5m)

Unique hosts (currently reporting)

Total events (since start) (or per minute)

Active containers

Protocol distribution: Pie chart (TCP/UDP/Others)

Top processes: table with columns: Process Name, Count (last 1m), Failed connects (ratio)

Events timeline: streaming time-series line chart (events/sec), use kernel_timestamp_ns → aggregated per second

Quick filters: host, container, protocol, process text search

Live stream preview: small virtualized list showing latest 10 events

Interaction:

Clicking a top process drills to Processes page with filtered view.

Page: Live Stream

Purpose: canonical demo view — show raw events in streaming table and enable drill-down.

Components:

Toolbar: Pause/Resume stream, Clear buffer, Auto-scroll toggle, Export CSV (last N events), Mark event (feedback).

Filters bar: host selector, process search, protocol checkboxes, success/failure toggle, time window selector (last 10s/60s/5m/custom).

Virtualized Event Table (high-performance):

Columns:

Time (humanized using timestamp + kernel precision)

Host

PID

Process Name

Syscall

Protocol

Src IP:port → format ip:port

Dst IP:port

Container ID (short 8 chars)

Success (green/red)

Actions (Details, Flag)

Rows: live, append-only until pause/clear.

Each row clickable to open Event Detail modal.

Event Detail Modal:

Full JSON raw view

Fields grouped: process, network, container, timestamps

Actions: Flag/Label (POST /api/events/:id/label), Export this event (download JSON), Copy JSON

Timeline snippet: show last 10 events for same PID

Interaction:

Search filters apply server-side (if REST search supported) or client-side if only WebSocket available. For large datasets, prefer server-side filter.

Page: Hosts / Containers / Processes

Purpose: aggregated views and pivoting.

Hosts page: list of hosts; for each: last seen timestamp, events/sec, number of processes, health status. Click host to open host detail (filtered live stream).

Containers page: container id, image (if provided), PID list, top destinations.

Processes page: process name index; for each process show connect count, failed ratio, unique dsts, top hosts.

Page: Flow Explorer (optional advanced)

Visualize connection graph (small): node = process or container; edge = connection (aggregated). Use simple force graph (vis.js) or draw a Sankey/Edge list. Minimum: show edges between host/process -> dst_ip.

Page: Settings

Connection settings: backend URL, WebSocket endpoint, sample rate, demo mode toggle.

Schema version: display current schema (v1.0).

Export/Import configuration

Authentication: login token.

6. API / Backend contract (exact endpoints)

1) WebSocket (primary for live demo)

URL: ws(s)://<backend>/ws/telemetry

Behavior:

Immediately starts streaming validated JSON events (same schema).

Heartbeat/ping messages from server every 30s.

Client can send control messages (JSON) to server:

{ "type": "pause" } — server will stop pushing new events to the socket (but continue ingesting)

{ "type": "resume" }

{ "type": "subscribe", "filter": {...} } — optional, to ask server to filter events

Server messages:

{ "type":"event", "data": <event_json> }

{ "type":"heartbeat" }

{ "type":"stats", "data": { events_per_sec: X, ... } }

Notes: if backend supports per-client filters, implement subscribe. Otherwise client can filter locally.

2) REST endpoints (for search, aggregates, actions)

All JSON, authenticated (token) if environment requires.

GET /api/events?limit=N&since=epoch_secs&host=...&process=...&protocol=...&success=true|false
→ returns array of events (most recent first). Support pagination: ?offset=... or ?cursor=....

GET /api/events/:event_id
→ returns single event JSON (detailed).

POST /api/events/:event_id/label
Body: { "label": "suspicious", "notes": "reason" } → returns 200.

GET /api/stats?window=10s
→ { events_per_sec: x, tcp_count: y, udp_count: z, unique_hosts: n, unique_containers: m }

GET /api/hosts
→ list of hosts with basic metrics.

GET /api/processes?host=...
→ process summary list.

POST /api/replay (demo) — optional
Body: { "file": "sample_name", "rate": 100 } — backend streams sample events to telemetry topic for demo.

3) Health & status

GET /api/status → { kafka_connected: true, bpf_agent_seen: true, last_event_ts: epoch }

7. Data flow & client behavior

Use WebSocket as primary live feed. On connect, show connection status badge. If WS fails, fallback to polling GET /api/events?limit=... every 2s (graceful degrade).

Maintain a bounded in-memory circular buffer of events (configurable, default 10,000 rows). Do not keep infinite in memory.

Use virtualization (react-window) for the event list so that thousands of rows do not freeze the UI.

When user sets filters, ideally send them to backend (subscribe/filter) to reduce client network load. If backend lacks filter support, apply client-side filters and document the limitations.

Provide pause to stop appending new rows (useful for demo speech).

Auto-scroll toggle: when on, table should scroll to newest event. When off, don't interfere with user browsing older rows.

8. UI/UX design details
Visual language

Clean, dark or light theme (choose consistent). Use Tailwind with neutral palette.

Use rounded cards, subtle shadows — professional SOC look.

Use green/red chips for success/failure.

Humanize times: timeago for recency and full timestamp in detail modal.

Fonts & Iconography

System font stack, or Inter.

Icon set: Heroicons or FontAwesome.

Responsive behavior

Desktop-first. On small screens show simplified view (only live stream and filters).

9. Charts & components specifics

Events per second chart: sampled per-second using kernel timestamps. Chart should show last 60s by default; live-update append.

Protocol pie: counts of TCP/UDP/Others over window.

Top processes: sortable table (process name, count, failed ratio).

Geo map: optional — not required (IP -> geo enrichment could be done in backend).

Event detail JSON viewer: collapsible JSON (use react-json-view).

10. UX interactions (detailed examples)

Click row → Open modal: show fields, link to host/process/ container views (click host to go to host page and apply filter).

Flagging an event: click “flag” on row → POST /api/events/:id/label → show toast.

Export: export CSV of currently shown (filtered) events.

Pause: clicking Pause switches to paused state and disables websocket appends (or ignore incoming messages until resume).

Search: text search should match process_name, pid, src_ip, dst_ip, container_id — use regex-friendly search.

11. Performance, scale & backpressure

Frontend must be resilient:

Maintain a max in-memory events buffer; default 10k rows — configurable via Settings.

Throttle UI updates: if incoming event rate > 1000/sec, batch UI updates at 200ms intervals to avoid reflows.

Use virtualization for the table.

Use incremental chart decimation (downsampling) for long time-series.

When backend signals stats message indicating overload, show a warning and increase UI throttling.

12. Security & privacy considerations

Do not display long raw command lines or sensitive data. We only have metadata; still sanitize any strings before inserting into DOM.

Protect REST endpoints with authentication (JWT) in production.

Use HTTPS / WSS for production.

CORS: restrict origins.

Sanitize user-supplied labels/comments to prevent XSS.

13. Accessibility & usability

Keyboard navigable table rows (Enter opens modal).

Sufficient color contrast for red/green.

ARIA roles for the table and modals.

14. Development setup & running locally

Frontend dev:

git clone <repo>

cd acds/ui

npm install

.env.local:

VITE_API_BASE=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws/telemetry

npm run dev (vite) or npm start (create-react-app).

For demo without backend: provide mock/ws-mock.json and scripts/mock-ws.js to replay events into the client.

Docker:

Provide Dockerfile and docker-compose.ui.yml for one-click deploy (build UI and reverse-proxy with Nginx). Use environment variable injection for backend URL.

15. Testing & QA

Unit tests: component snapshot & logic (Jest + React Testing Library).

Integration tests: simulate websocket stream and assert table updates.

End-to-end: Cypress script that:

opens UI

connects to mock WS

verifies 10 events appended

verifies filters

Load test: simulate 5k events replay and verify UI stays responsive (virtualization + throttling).

16. Accessibility and Documentation for demo script

Provide a short demo script (what to say & which buttons to press) — I can provide that separately.

Provide a README acds/ui/README.md with start instructions, env variables, and API contract.

17. Acceptance criteria / checklist (deliverable requirements)

 Live WebSocket connection status visible (connected/disconnected/reconnecting)

 Table shows live events and can be paused/resumed

 Filters for host, process, protocol, container, success/failure work

 Event Detail modal shows full JSON and actions (flag, export)

 Charts: events/sec, protocol pie, top processes implemented and update live

 Virtualized table to handle 10k+ events without visible UI lag

 Export CSV for visible rows

 Authentication stubbed or implemented

 Docker build + Nginx reverse proxy available

 E2E test script exists and passes locally with mock data

18. Sample UI wireframes (textual)

Dashboard layout (desktop):

+---------------------------------------------------------------+
| Header: [ACDS Telemetry] [Host select] [Kafka status: green]  |
+------------------+----------------------------+--------------+
| Sidebar          | Main (Dashboard)           | Right panel  |
| - Dashboard      | KPIs row                   | Alerts /     |
| - Live Stream    | Protocol pie | Events/sec | Notifications |
| - Hosts          | Top Processes table        |              |
| - Processes      | Timeline chart (60s)       |              |
+------------------+----------------------------+--------------+

Live Stream:

+---------------------------------------------------------------+
| Toolbar: [Pause] [Auto-scroll] [Export] [Filters]             |
+---------------------------------------------------------------+
| Virtualized Event Table (columns noted above)                 |
+---------------------------------------------------------------+
| Event Detail (modal)                                          |
+---------------------------------------------------------------+

19. Implementation tips & gotchas (developer notes)

Time handling: prefer to use kernel_timestamp_ns for ordering and compute epoch using backend boot-time offset if needed. Show both human epoch and relative time.

Return_code sign: ensure the backend/consumer converts 32-bit unsigned to signed ints or do so in frontend by new Int32Array([value])[0].

Container ID: show shortened (first 8-12 chars). Link to container detail.

IPv6 handling: display IPv6 addresses in bracket form when combined with ports (e.g. [::1]:80).

Backpressure: the backend should implement rate limiting; frontend should gracefully drop events older than buffer cap.

Testing network differences: WSL and docker internal IPs will show 127.0.0.1, 172.* etc. Document differences in README.

20. Deliverables for handoff to frontend dev

Provide these files/folders to the frontend dev:

acds/docs/telemetry_schema_v1.md (schema, caveats, UDP semantics).

acds/docs/telemetry_to_dpi_contract.md (topic name, retention, partitioning hints).

Example event file: acds/ui/mock/events_sample.json (100 sample events covering IPv4, IPv6, UDP, TCP, execve).

Endpoints spec: acds/ui/api_spec.md (contains REST + WS described above).

acds/ui/README.md with run instructions and demo script.

acds/telemetry/tests/load_validation.sh for backend load testing.

UI wireframe images (optional) or ASCII wireframes above.

Token for demo auth (if required).

21. Timeline & effort estimate (suggested sprint plan)

Day 0: Setup repo, skeleton app, env config. (0.5 day)

Day 1: Implement WebSocket client, event buffer, virtualized live table, header, sidebar. (1 day)

Day 2: Implement filters + event detail modal + export CSV. (1 day)

Day 3: Charts (events/sec, protocol pie, top processes) and host/process pages. (1 day)

Day 4: Polish CSS/Tailwind, make responsive, add tests and mock dataset. (1 day)

Day 5: Dockerize + create demo README + runthrough. (0.5 day)

22. Example code snippets

WebSocket consumer (pseudo, React hook)

// useTelemetry.js
import { useEffect, useRef, useState } from 'react';
export function useTelemetry(wsUrl) {
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState([]);
  const wsRef = useRef(null);
  useEffect(() => {
    const ws = new WebSocket(wsUrl);
    ws.onopen = () => setConnected(true);
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === 'event') {
        setEvents(prev => {
          const copy = prev.slice(-9999); // keep size bounded
          copy.push(msg.data);
          return copy;
        });
      }
    };
    ws.onclose = () => setConnected(false);
    wsRef.current = ws;
    return () => { ws.close(); }
  }, [wsUrl]);
  return { connected, events, ws: wsRef.current };
}

Render row snippet

<td>{new Date(event.timestamp * 1000).toLocaleTimeString()}</td>
<td>{event.host_id}</td>
<td>{event.pid}</td>
<td>{event.process_name}</td>
<td>{event.protocol}</td>
<td>{\`\${event.src_ip}:\${event.src_port}\`}</td>
<td>{\`\${event.dst_ip}:\${event.dst_port}\`}</td>
<td><span className={event.success ? 'text-green-500':'text-red-500'}>{event.success ? 'OK' : 'FAIL'}</span></td>

23. Acceptance demo script (what you show to teacher)

Open the app → show header badges (Kafka connected).

Go to Dashboard: show KPI & charts updating.

Switch to Live Stream: show live events populating.

Generate traffic (curl/ping) — events appear; highlight TCP/UDP detection.

Click a row → open details, show container_id and kernel timestamp.

Pause stream, search for a process name, demonstrate filter.

Flag an event, show POST success.

Export current view to CSV.

Conclude: explain how DPI will consume telemetry.
