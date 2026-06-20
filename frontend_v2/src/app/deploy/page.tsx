"use client";

import { useEffect, useState } from "react";
import { getPatrol } from "@/lib/api";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceDot } from "recharts";

import { useSearchParams } from "next/navigation";

function DeployContent() {
  const searchParams = useSearchParams();
  const units = parseInt(searchParams.get("units") || "20", 10);
  
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    getPatrol(units).then((res) => {
      setData(res);
      setLoading(false);
    });
  }, [units]);

  const assignments = data?.assignments || [];
  const coverageCurve = data?.coverage_curve || [];
  const covPct = data?.coverage_pct || 0;

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
          Assign units to 3-5 hotspot optimal patrol routes to maximize high-priority coverage. Greedy spatial de-bunching ensures spread and prevents overlapping patrols.
        </p>
      </header>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-transparent border border-border p-8 flex flex-col justify-between">
          <div className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary mb-8">Units Deployed</div>
          <div className="text-4xl font-light text-text-primary tracking-tight">{data?.units || 0}</div>
        </div>
        <div className="bg-transparent border border-border p-8 flex flex-col justify-between">
          <div className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary mb-8">Priority Coverage</div>
          <div className="text-4xl font-light text-patrol tracking-tight">{covPct.toFixed(1)}%</div>
        </div>
      </div>

      {/* Coverage Curve */}
      <div className="border border-border p-8">
        <h2 className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary mb-6">Coverage Efficiency</h2>
        <div className="h-[400px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={coverageCurve} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2F333D" vertical={false} />
              <XAxis dataKey="units" stroke="#9CA3AF" tick={{ fontSize: 12, fill: '#9CA3AF' }} tickMargin={10} />
              <YAxis stroke="#9CA3AF" tick={{ fontSize: 12, fill: '#9CA3AF' }} tickMargin={10} domain={[0, 100]} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#000', borderColor: '#222', color: '#fff' }}
              />
              <Line type="monotone" dataKey="coverage_pct" stroke="#ffffff" strokeWidth={3} dot={false} />
              <ReferenceDot x={units} y={covPct} r={6} fill="#10B981" stroke="none" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Roster Table */}
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
  );
}

import { Suspense } from "react";
export default function DeployPage() {
  return <Suspense fallback={<div>Loading...</div>}><DeployContent /></Suspense>;
}
