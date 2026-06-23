"use client";

import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import { Users, AlertTriangle, MapPin, Hash, CheckCircle2, Download } from "lucide-react";
import { useWatchlist } from "@/lib/hooks/useWatchlist";

export default function RepeatOffendersPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const { watchlist, toggleWatchlist } = useWatchlist();
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const handlePin = (hotspotId: string) => {
    if (!hotspotId) return;
    toggleWatchlist(hotspotId);
    
    const isNowPinned = !watchlist.includes(hotspotId);
    if (isNowPinned) {
      setToastMessage(`${hotspotId} pinned! View it on the Live Map.`);
    } else {
      setToastMessage(`${hotspotId} removed from Live Map.`);
    }
    
    // Hide toast after 3 seconds
    setTimeout(() => setToastMessage(null), 3000);
  };

  useEffect(() => {
    fetchApi("/repeat-offenders", { limit: 50 }).then((res) => {
      setData(res);
      setLoading(false);
    });
  }, []);

  if (loading)
    return (
      <div className="p-8 text-text-muted animate-pulse">
        Loading repeat-offender data...
      </div>
    );

  const offenders = data?.offenders || [];
  const totalRepeat = data?.total_repeat_vehicles || 0;
  const pctOfTotal = data?.pct_of_total_violations || 0;
  const centroids = data?.centroids || [];

  // Tier → badge styling. Ordered least → most concerning.
  const tierStyle: Record<string, string> = {
    Occasional: "bg-text-primary/5 text-text-secondary border-border",
    Frequent: "bg-amber-900/30 text-amber-400 border-amber-500/40",
    Habitual: "bg-critical/15 text-critical border-critical/40",
  };
  const tierBadge = (tier?: string) =>
    tier ? (
      <span
        className={`px-2.5 py-1 rounded text-[10px] font-medium tracking-widest uppercase border ${
          tierStyle[tier] ?? tierStyle.Occasional
        }`}
      >
        {tier}
      </span>
    ) : (
      <span className="text-text-muted">-</span>
    );

  // Concentration stat: top 10 offenders' share
  const top10Sum = offenders
    .slice(0, 10)
    .reduce((s: number, o: any) => s + o.violation_count, 0);

  const exportCSV = () => {
    if (!offenders.length) return;
    const headers = ["Vehicle ID", "Risk Tier", "Violations", "Reoffend Gap (days)", "Top Station", "Top Hotspot", "Distinct Locations", "Distinct Hotspots"];
    const rows = offenders.map((row: any) => [
      row.vehicle_number,
      row.risk_tier ?? "",
      row.violation_count,
      row.avg_days_between ?? "",
      `"${row.top_location}"`,
      row.top_hotspot,
      row.distinct_locations,
      row.distinct_hotspots
    ]);
    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map((e: any[]) => e.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `trinetra_repeat_offenders.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="p-12 max-w-7xl mx-auto space-y-12 bg-bg-base min-h-screen">
      <header className="space-y-4">
        <h1 className="text-5xl font-light tracking-tight text-text-primary">
          REPEAT OFFENDERS
        </h1>
        <p className="text-text-secondary font-light text-sm tracking-wide max-w-2xl">
          Chronic violators identified by anonymised vehicle ID. Vehicle numbers
          are PII-masked. Frequency stats are valid, real-world identity is not
          exposed.
        </p>
      </header>

      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed top-8 right-8 z-50 bg-bg-surface border border-border text-text-primary px-6 py-4 rounded-xl shadow-2xl flex items-center gap-3 animate-in fade-in slide-in-from-top-4">
          <CheckCircle2 size={18} className="text-emerald-500" />
          <span className="text-sm font-medium tracking-wide">{toastMessage}</span>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-transparent border border-border p-8">
          <div className="flex items-center justify-between mb-8">
            <div className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary">
              Repeat Vehicles
            </div>
            <Users
              size={16}
              className="text-text-primary"
              strokeWidth={1}
            />
          </div>
          <div className="text-4xl font-light text-text-primary tracking-tight">
            {totalRepeat.toLocaleString()}
          </div>
          <div className="text-[10px] text-text-secondary mt-2 tracking-wide">
            vehicles with ≥3 violations over ≥7 days
          </div>
        </div>

        <div className="bg-transparent border border-border p-8">
          <div className="flex items-center justify-between mb-8">
            <div className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary">
              Share of All Violations
            </div>
            <AlertTriangle
              size={16}
              className="text-text-primary"
              strokeWidth={1}
            />
          </div>
          <div className="text-4xl font-light text-critical tracking-tight">
            {pctOfTotal.toFixed(1)}%
          </div>
          <div className="text-[10px] text-text-secondary mt-2 tracking-wide">
            of total violations from repeaters
          </div>
        </div>

        <div className="bg-transparent border border-border p-8">
          <div className="flex items-center justify-between mb-8">
            <div className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary">
              Worst Offender
            </div>
            <Hash
              size={16}
              className="text-text-primary"
              strokeWidth={1}
            />
          </div>
          <div className="text-4xl font-light text-text-primary tracking-tight">
            {offenders[0]?.violation_count || 0}
          </div>
          <div className="text-[10px] text-text-secondary mt-2 tracking-wide">
            violations by a single vehicle
          </div>
        </div>

        <div className="bg-transparent border border-border p-8">
          <div className="flex items-center justify-between mb-8">
            <div className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary">
              Top 10 Concentration
            </div>
            <MapPin
              size={16}
              className="text-text-primary"
              strokeWidth={1}
            />
          </div>
          <div className="text-4xl font-light text-text-primary tracking-tight">
            {top10Sum}
          </div>
          <div className="text-[10px] text-text-secondary mt-2 tracking-wide">
            violations by top 10 vehicles
          </div>
        </div>
      </div>

      {/* Behavioural tiers — K-Means cluster centroids (ML explainer) */}
      {centroids.length > 0 && (
        <div>
          <h2 className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary mb-2">
            Behavioural Tiers
          </h2>
          <p className="text-text-secondary font-light text-xs tracking-wide max-w-2xl mb-6">
            K-Means clusters offenders on three behavioural signals — volume,
            frequency, and reoffend interval. Tiers are ranked, not thresholded:
            Frequent = intense but short-lived; Habitual = sustained high volume.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {centroids.map((c: any) => (
              <div key={c.risk_tier} className="bg-transparent border border-border p-8">
                <div className="flex items-center justify-between mb-6">
                  {tierBadge(c.risk_tier)}
                  <span className="text-[10px] text-text-secondary tracking-wide">
                    {c.vehicle_count.toLocaleString()} vehicles
                  </span>
                </div>
                <dl className="space-y-3 text-xs">
                  <div className="flex justify-between">
                    <dt className="text-text-secondary tracking-wide">Avg violations</dt>
                    <dd className="text-text-primary font-light">{c.total_violations.toFixed(1)}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-text-secondary tracking-wide">Per day</dt>
                    <dd className="text-text-primary font-light">{c.frequency.toFixed(2)}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-text-secondary tracking-wide">Reoffend gap</dt>
                    <dd className="text-text-primary font-light">{c.avg_days_between.toFixed(1)} days</dd>
                  </div>
                </dl>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Table */}
      <div>
        <div className="flex justify-between items-end mb-6">
          <h2 className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary">Offenders Watchlist</h2>
          <button 
            onClick={exportCSV}
            disabled={!offenders.length}
            className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-text-primary hover:text-white transition-colors bg-text-primary/5 hover:bg-text-primary/10 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 border border-border"
          >
            <Download size={14} /> Export CSV
          </button>
        </div>
        <div className="border border-border overflow-hidden">
          <table className="w-full text-sm text-left">
          <thead className="text-[10px] text-text-secondary uppercase tracking-[0.2em] font-medium border-b border-border bg-text-primary/5">
            <tr>
              <th className="px-8 py-6">#</th>
              <th className="px-8 py-6">Vehicle ID</th>
              <th className="px-8 py-6">Tier</th>
              <th className="px-8 py-6 text-right">Violations</th>
              <th className="px-8 py-6 text-right">Gap (days)</th>
              <th className="px-8 py-6">Top Station</th>
              <th className="px-8 py-6">Top Hotspot</th>
              <th className="px-8 py-6 text-right">Locations</th>
              <th className="px-8 py-6 text-right">Hotspots</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {offenders.map((row: any, i: number) => (
              <tr
                key={`${row.vehicle_number}-${i}`}
                className="hover:bg-text-primary/5 transition-colors"
              >
                <td className="px-8 py-6 text-text-muted">{i + 1}</td>
                <td className="px-8 py-6 font-mono text-text-primary text-xs">
                  {row.vehicle_number}
                </td>
                <td className="px-8 py-6">
                  {tierBadge(row.risk_tier)}
                </td>
                <td className="px-8 py-6 text-right font-light text-text-primary">
                  {row.violation_count}
                </td>
                <td className="px-8 py-6 text-right text-text-secondary font-light">
                  {row.avg_days_between != null ? row.avg_days_between.toFixed(1) : "-"}
                </td>
                <td className="px-8 py-6 text-text-secondary font-light">
                  {row.top_location}
                </td>
                <td className="px-8 py-6 text-text-secondary font-light">
                  {row.top_hotspot ? (
                    <button 
                      onClick={() => handlePin(row.top_hotspot)}
                      className={`px-3 py-1.5 rounded transition-colors text-xs font-medium tracking-widest uppercase border ${
                        watchlist.includes(row.top_hotspot) 
                          ? 'bg-fuchsia-900/40 text-fuchsia-400 border-fuchsia-500/50' 
                          : 'bg-text-primary/5 hover:bg-text-primary/10 border-border'
                      }`}
                    >
                      {watchlist.includes(row.top_hotspot) ? 'Tracking ✓' : 'Track on Map'} {row.top_hotspot}
                    </button>
                  ) : (
                    "-"
                  )}
                </td>
                <td className="px-8 py-6 text-right text-text-primary font-light">
                  {row.distinct_locations}
                </td>
                <td className="px-8 py-6 text-right text-text-primary font-light">
                  {row.distinct_hotspots}
                </td>
              </tr>
            ))}
            {offenders.length === 0 && (
              <tr>
                <td
                  colSpan={9}
                  className="px-8 py-12 text-center text-text-secondary font-light tracking-wide"
                >
                  No repeat-offender data available.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
    </div>
  );
}
