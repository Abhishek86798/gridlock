"use client";

import { useEffect, useState } from "react";
import { getPatrol, getStationForecast } from "@/lib/api";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceDot } from "recharts";
import { Download, AlertTriangle, ShieldCheck, TrendingUp } from "lucide-react";

import { useSearchParams } from "next/navigation";

function DeployContent() {
  const searchParams = useSearchParams();
  const units = parseInt(searchParams.get("units") || "20", 10);
  
  const [data, setData] = useState<any>(null);
  const [peakShiftByStation, setPeakShiftByStation] = useState<Record<string, any[]>>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    Promise.all([getPatrol(units), getStationForecast()]).then(([patrol, stationForecast]) => {
      setData(patrol);
      const lookup: Record<string, any[]> = {};
      for (const row of stationForecast.forecast || []) {
        if (row.peak_shifts?.length) lookup[row.police_station] = row.peak_shifts;
      }
      setPeakShiftByStation(lookup);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [units]);

  const assignments = data?.assignments || [];
  const coverageCurve = data?.coverage_curve || [];
  const covPct = data?.coverage_pct || 0;
  const predCovered = data?.predicted_violations_covered ?? 0;
  const predTotal = data?.total_predicted_load ?? 0;
  const predPct = data?.pct_predicted_covered ?? 0;
  const escalationWatch = data?.escalation_watch || [];
  const uncoveredCount = escalationWatch.filter((e: any) => !e.covered).length;

  const exportCSV = () => {
    if (!assignments.length) return;
    const headers = ["Unit #", "Patrol Route", "Risk Score", "Window"];
    const rows = assignments.map((row: any) => [
      row.unit_id,
      `"${row.route?.join(" -> ") || row.hotspot_id}"`, // quote to handle spaces and arrows
      row.risk_score?.toFixed(1),
      row.time_window
    ]);
    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map((e: any[]) => e.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `trinetra_patrol_roster_${units}_units.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  if (loading) {
    return (
      <div className="p-12 max-w-7xl mx-auto min-h-screen flex items-center justify-center">
        <div className="text-text-secondary animate-pulse tracking-[0.2em] uppercase font-light text-sm">
          Calculating optimal deployment routes...
        </div>
      </div>
    );
  }

  return (
    <div className="p-12 max-w-7xl mx-auto space-y-12 bg-bg-base min-h-screen">
      <header className="space-y-4">
        <h1 className="text-5xl font-light tracking-tight text-text-primary">DEPLOYMENT</h1>
        <p className="text-text-secondary font-light text-sm tracking-wide max-w-2xl">
          Units are allocated against next week&apos;s <span className="text-text-primary">predicted</span> load,
          then spread with greedy spatial de-bunching. The forecast agrees with history ~95% — the dangerous
          hotspots are stably dangerous — so the value isn&apos;t a higher coverage number; it&apos;s the
          <span className="text-critical"> Escalation Watch</span> below, which flags the rising hotspots a
          history-only allocation under-weights.
        </p>
      </header>

      <p className="text-[10px] text-text-secondary font-light tracking-wide -mt-6">
        Adjust <span className="text-text-primary">Patrol Units</span> in the left sidebar to recalculate coverage and the roster below.
      </p>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-transparent border border-border p-8 flex flex-col justify-between">
          <div className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary mb-8">Units Deployed</div>
          <div className="text-4xl font-light text-text-primary tracking-tight">{data?.units || 0}</div>
        </div>
        <div className="bg-transparent border border-border p-8 flex flex-col justify-between">
          <div className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary mb-8">Predicted Violations Covered</div>
          <div className="text-4xl font-light text-text-primary tracking-tight">
            {Math.round(predCovered).toLocaleString()}
            <span className="text-lg text-text-secondary"> of {Math.round(predTotal).toLocaleString()}</span>
          </div>
          <div className="text-[10px] text-text-secondary mt-2 tracking-wide">
            {predPct.toFixed(1)}% of next week&apos;s predicted load
          </div>
        </div>
        <div className="bg-transparent border border-border p-8 flex flex-col justify-between">
          <div className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary mb-8">Priority Coverage</div>
          <div className={`text-4xl font-light tracking-tight ${covPct < 60 ? 'text-critical' : covPct < 80 ? 'text-amber-400' : 'text-patrol'}`}>{covPct.toFixed(1)}%</div>
          <div className="text-[10px] text-text-secondary mt-2 tracking-wide">of high-risk zones covered — {(100 - covPct).toFixed(1)}% remain unpatrolled</div>
        </div>
      </div>

      {/* Coverage Curve */}
      <div className="border border-border p-8">
        <h2 className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary mb-6">Coverage Efficiency</h2>
        <div className="h-[400px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={coverageCurve} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2F333D" vertical={false} />
              <XAxis dataKey="units" stroke="#9CA3AF" tick={{ fontSize: 12, fill: '#9CA3AF' }} tickMargin={10} label={{ value: 'Patrol Units', position: 'insideBottom', offset: -5, fill: '#9CA3AF', fontSize: 11 }} />
              <YAxis stroke="#9CA3AF" tick={{ fontSize: 12, fill: '#9CA3AF' }} tickMargin={10} domain={[0, 100]} label={{ value: 'Hotspot Coverage %', angle: -90, position: 'insideLeft', fill: '#9CA3AF', fontSize: 11 }} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#000', borderColor: '#222', color: '#fff' }}
              />
              <Line type="monotone" dataKey="coverage_pct" stroke="#ffffff" strokeWidth={3} dot={false} />
              <ReferenceDot x={units} y={covPct} r={6} fill="#10B981" stroke="none" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Escalation Watch — forward-looking signal: rising hotspots */}
      {escalationWatch.length > 0 && (
        <div className="border border-border p-8">
          <div className="flex items-center gap-3 mb-2">
            <TrendingUp size={16} className="text-critical" strokeWidth={1.5} />
            <h2 className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary">
              Escalation Watch
            </h2>
          </div>
          <p className="text-text-secondary font-light text-xs tracking-wide max-w-2xl mb-6">
            Hotspots where next week's predicted load is rising vs baseline. The
            allocation covers stable high-volume hotspots; these are the rising
            ones —{" "}
            <span className="text-critical">
              {uncoveredCount} unstaffed
            </span>{" "}
            by the current {data?.units}-unit deployment.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...escalationWatch]
              .sort((a: any, b: any) => Number(a.covered) - Number(b.covered) || b.count_delta - a.count_delta)
              .map((e: any) => (
                <div
                  key={e.hotspot_id}
                  className={`border p-5 ${
                    e.covered ? "border-border" : "border-critical/40 bg-critical/5"
                  }`}
                >
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-mono text-text-primary text-xs">{e.hotspot_id}</span>
                    {e.covered ? (
                      <span className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest text-emerald-500">
                        <ShieldCheck size={13} /> Covered
                      </span>
                    ) : (
                      <span className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest text-critical">
                        <AlertTriangle size={13} /> Unstaffed
                      </span>
                    )}
                  </div>
                  <div className="text-text-secondary text-xs font-light tracking-wide mb-3">
                    {e.police_station || "—"}
                  </div>
                  <div className="flex items-baseline gap-2">
                    <span className="text-2xl font-light text-text-primary">
                      {e.baseline_count} → {Math.round(e.predicted_count)}
                    </span>
                    <span className="text-sm text-critical font-light">+{e.change_pct}%</span>
                  </div>
                  <div className="text-[10px] text-text-secondary mt-1 tracking-wide">
                    predicted violations next week
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Station Peak Shifts — top stations by predicted load with shift breakdown */}
      {Object.keys(peakShiftByStation).length > 0 && (
        <div className="border border-border p-8">
          <h2 className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary mb-1">Station Shift Windows</h2>
          <p className="text-[10px] text-text-secondary/60 mb-6 font-light">Top stations by predicted load — peak patrol windows derived from historical hour×day patterns.</p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.entries(peakShiftByStation).slice(0, 6).map(([station, shifts]) => (
              <div key={station} className="border border-border p-5">
                <div className="text-[10px] font-light text-text-secondary uppercase tracking-widest mb-3 truncate">{station}</div>
                <div className="flex flex-col gap-1.5">
                  {shifts.map((ps: any, i: number) => (
                    <div key={i} className="flex items-center justify-between">
                      <span className="text-xs font-light text-text-primary">{ps.day} · {ps.shift}</span>
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-1 bg-border rounded-full overflow-hidden">
                          <div className="h-full bg-patrol rounded-full" style={{ width: `${Math.min(ps.pct * 3, 100)}%` }} />
                        </div>
                        <span className="text-[10px] text-text-muted w-8 text-right">{ps.pct}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Roster Table */}
      <div>
        <div className="flex justify-between items-end mb-6">
          <h2 className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary">Assignments Roster</h2>
          <button 
            onClick={exportCSV}
            disabled={!assignments.length}
            className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-text-primary hover:text-white transition-colors bg-text-primary/5 hover:bg-text-primary/10 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 border border-border"
          >
            <Download size={14} /> Export CSV
          </button>
        </div>
        <div className="border border-border overflow-hidden">
          <table className="w-full text-sm text-left">
          <thead className="text-[10px] text-text-secondary uppercase tracking-[0.2em] font-medium border-b border-border bg-text-primary/5">
            <tr>
              <th className="px-8 py-6">Unit #</th>
              <th className="px-8 py-6">Patrol Route</th>
              <th className="px-8 py-6 text-right">Risk Score</th>
              <th className="px-8 py-6 text-right">Window</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {assignments.map((row: any, i: number) => (
              <tr key={i} className="hover:bg-text-primary/5 transition-colors">
                <td className="px-8 py-6 font-medium text-text-secondary">{row.unit_id}</td>
                <td className="px-8 py-6 font-light text-text-primary text-xs tracking-wide">{row.route?.join(" → ") || row.hotspot_id}</td>
                <td className="px-8 py-6 text-right font-light text-text-primary">{row.risk_score?.toFixed(1)}</td>
                <td className="px-8 py-6 text-right font-light text-text-secondary">{row.time_window}</td>
              </tr>
            ))}
            {assignments.length === 0 && (
              <tr>
                <td colSpan={4} className="px-8 py-12 text-center text-text-secondary font-light tracking-wide">No units deployed.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
    </div>
  );
}

import { Suspense } from "react";
export default function DeployPage() {
  return <Suspense fallback={<div>Loading...</div>}><DeployContent /></Suspense>;
}
