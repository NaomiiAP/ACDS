import React, { useState, useMemo, useRef, useEffect, useContext } from 'react';
import { TelemetryContext } from '../context/TelemetryContext';
import { FixedSizeList as List } from 'react-window';
import { Play, Pause, Trash2, Download, Search, AlertCircle, X, ChevronDown } from 'lucide-react';
import { format } from 'date-fns';

function Modal({ event, onClose }) {
    if (!event) return null;
    return (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
            <div className="bg-slate-800 border border-slate-700 rounded-xl shadow-2xl w-full max-w-3xl overflow-hidden flex flex-col max-h-[90vh]">
                <div className="px-6 py-4 border-b border-slate-700 flex justify-between items-center bg-slate-800/50">
                    <h3 className="text-lg font-semibold text-slate-200">Event Details</h3>
                    <button onClick={onClose} className="text-slate-400 hover:text-white transition cursor-pointer">
                        <X className="h-5 w-5" />
                    </button>
                </div>
                <div className="p-6 overflow-y-auto font-mono text-sm text-slate-300">
                    <pre className="bg-slate-900 p-4 rounded-lg border border-slate-800 overflow-x-auto">
                        {JSON.stringify(event, null, 2)}
                    </pre>
                </div>
                <div className="px-6 py-4 border-t border-slate-700 bg-slate-800/50 flex justify-end gap-3">
                    <button onClick={() => alert("Flagged!")} className="px-4 py-2 bg-rose-500/10 text-rose-400 border border-rose-500/50 hover:bg-rose-500/20 rounded-md font-medium transition cursor-pointer">
                        Flag Suspicious
                    </button>
                    <button onClick={onClose} className="px-4 py-2 bg-slate-700 text-slate-200 hover:bg-slate-600 border border-slate-600 rounded-md font-medium transition cursor-pointer">
                        Close
                    </button>
                </div>
            </div>
        </div>
    );
}

export default function LiveStream() {
    const contextProps = useContext(TelemetryContext) || {};
    const { events = [], isPaused, setIsPaused, clearBuffer } = contextProps;
    const [filterText, setFilterText] = useState("");
    const [protocolFilter, setProtocolFilter] = useState("ALL");
    const [autoScroll, setAutoScroll] = useState(true);
    const [selectedEvent, setSelectedEvent] = useState(null);

    const listRef = useRef(null);
    const containerRef = useRef(null);
    const [listHeight, setListHeight] = useState(600);

    useEffect(() => {
        if (containerRef.current) {
            setListHeight(containerRef.current.clientHeight);
        }
        const handleResize = () => {
            if (containerRef.current) setListHeight(containerRef.current.clientHeight);
        };
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    const filteredEvents = useMemo(() => {
        return events.filter(e => {
            if (protocolFilter !== "ALL" && e.protocol !== protocolFilter) return false;
            if (filterText) {
                const txt = filterText.toLowerCase();
                if (
                    !(e.process_name || "").toLowerCase().includes(txt) &&
                    !(e.src_ip || "").toLowerCase().includes(txt) &&
                    !(e.dst_ip || "").toLowerCase().includes(txt) &&
                    !(e.host_id || "").toLowerCase().includes(txt)
                ) {
                    return false;
                }
            }
            return true;
        });
    }, [events, filterText, protocolFilter]);

    // Hook to handle auto-scrolling
    useEffect(() => {
        if (autoScroll && listRef.current && filteredEvents.length > 0) {
            listRef.current.scrollToItem(filteredEvents.length - 1, "center");
        }
    }, [filteredEvents.length, autoScroll]);

    const handleExport = () => {
        const csvContent = "data:text/csv;charset=utf-8,"
            + ["Timestamp,Host,PID,Process,Syscall,Protocol,Src,Dst,Success"]
                .concat(filteredEvents.map(e =>
                    `${e.timestamp},${e.host_id},${e.pid},${e.process_name},${e.syscall},${e.protocol},${e.src_ip}:${e.src_port},${e.dst_ip}:${e.dst_port},${e.success}`
                ))
                .join("\n");

        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", `telemetry_export_${new Date().getTime()}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    const Row = ({ index, style }) => {
        const e = filteredEvents[index];
        const ts = new Date((e.timestamp || 0) * 1000);

        return (
            <div style={style}>
                <div
                    className={`flex items-center px-4 py-2 border-b border-slate-800/50 hover:bg-slate-700/30 cursor-pointer font-mono text-sm transition ${index % 2 === 0 ? 'bg-slate-800/20' : ''} h-full`}
                    onClick={() => setSelectedEvent(e)}
                >
                    <div className="w-1/12 text-slate-400">{format(ts, 'HH:mm:ss.SSS')}</div>
                    <div className="w-2/12 text-slate-300 truncate" title={e.host_id}>{e.host_id}</div>
                    <div className="w-1/12 text-emerald-300">{e.pid}</div>
                    <div className="w-2/12 font-bold text-slate-200 truncate">{e.process_name}</div>
                    <div className="w-1/12"><span className="px-2 py-0.5 rounded text-xs bg-slate-700 border border-slate-600">{e.protocol}</span></div>
                    <div className="w-2/12 text-green-300 truncate">{e.src_ip}:{e.src_port}</div>
                    <div className="w-2/12 text-teal-300 truncate">{e.dst_ip}:{e.dst_port}</div>
                    <div className="w-1/12 flex justify-center">
                        {e.success ? (
                            <span className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)]" title="Success"></span>
                        ) : (
                            <span className="w-2 h-2 rounded-full bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.8)]" title={`Failed: ${e.return_code}`}></span>
                        )}
                    </div>
                </div>
            </div>
        );
    };

    return (
        <div className="flex flex-col h-[calc(100vh-100px)] bg-slate-900 rounded-xl border border-slate-800 shadow-sm overflow-hidden p-0 m-0 w-full">
            {/* Toolbar */}
            <div className="p-4 bg-slate-800 border-b border-slate-700 flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setIsPaused(!isPaused)}
                        className={`flex items-center gap-2 px-3 py-1.5 rounded-md font-medium text-sm border cursor-pointer ${isPaused ? 'bg-amber-500/10 text-amber-500 border-amber-500/30 hover:bg-amber-500/20 transition-all' : 'bg-slate-700 text-slate-200 border-slate-600 hover:bg-slate-600 transition-colors'}`}
                    >
                        {isPaused ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
                        {isPaused ? 'Resume' : 'Pause'}
                    </button>

                    <button
                        onClick={clearBuffer}
                        className="flex items-center gap-2 px-3 py-1.5 rounded-md font-medium text-sm transition-colors border bg-slate-700 text-slate-200 border-slate-600 hover:bg-slate-600 cursor-pointer"
                        title="Clear Buffer"
                    >
                        <Trash2 className="h-4 w-4" /> Clear
                    </button>

                    <label className="flex items-center gap-2 px-3 py-1.5 cursor-pointer border border-slate-700 rounded-md bg-slate-800 text-sm text-slate-300 hover:text-white transition-colors group select-none">
                        <input
                            type="checkbox"
                            className="accent-emerald-500 rounded cursor-pointer"
                            checked={autoScroll}
                            onChange={(e) => setAutoScroll(e.target.checked)}
                        />
                        Auto-scroll
                    </label>
                </div>

                <div className="flex items-center gap-3">
                    <div className="relative">
                        <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                        <input
                            type="text"
                            placeholder="Search process, IP..."
                            value={filterText}
                            onChange={(e) => setFilterText(e.target.value)}
                            className="pl-9 pr-4 py-1.5 w-64 bg-slate-900 border border-slate-600 rounded-md text-sm text-slate-100 placeholder-slate-400 focus:outline-none focus:border-emerald-500"
                        />
                    </div>

                    <select
                        value={protocolFilter}
                        onChange={e => setProtocolFilter(e.target.value)}
                        className="px-3 py-1.5 bg-slate-900 border border-slate-600 rounded-md text-sm text-slate-200 focus:outline-none focus:border-emerald-500 cursor-pointer"
                    >
                        <option value="ALL">All Protocols</option>
                        <option value="TCP">TCP Only</option>
                        <option value="UDP">UDP Only</option>
                    </select>

                    <button
                        onClick={handleExport}
                        className="flex items-center gap-2 px-3 py-1.5 rounded-md font-medium text-sm border bg-emerald-500/10 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20 transition-all cursor-pointer"
                    >
                        <Download className="h-4 w-4" /> Export CSV
                    </button>
                </div>
            </div>

            {/* Table Header */}
            <div className="flex px-4 py-3 bg-slate-800/80 border-b border-slate-700 text-xs font-semibold text-slate-400 uppercase tracking-wider font-sans">
                <div className="w-1/12">Time</div>
                <div className="w-2/12">Host</div>
                <div className="w-1/12">PID</div>
                <div className="w-2/12">Process</div>
                <div className="w-1/12">Proto</div>
                <div className="w-2/12">Source</div>
                <div className="w-2/12">Destination</div>
                <div className="w-1/12 text-center">Status</div>
            </div>

            {/* Virtualized Table Body */}
            <div ref={containerRef} className="flex-1 bg-slate-900 w-full overflow-hidden">
                {filteredEvents.length > 0 ? (
                    <List
                        ref={listRef}
                        height={listHeight}
                        itemCount={filteredEvents.length}
                        itemSize={44}
                        width="100%"
                        overscanCount={5}
                    >
                        {Row}
                    </List>
                ) : (
                    <div className="flex flex-col items-center justify-center h-full text-slate-500 space-y-3">
                        <AlertCircle className="h-10 w-10 text-slate-600" />
                        <p className="text-lg font-medium">No events match the current filter</p>
                        {events.length === 0 && <p className="text-sm">Waiting for incoming telemetry stream...</p>}
                    </div>
                )}
            </div>

            <Modal event={selectedEvent} onClose={() => setSelectedEvent(null)} />
        </div>
    );
}
