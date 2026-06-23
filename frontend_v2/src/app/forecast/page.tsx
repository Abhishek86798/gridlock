"use client";

import { useEffect, useState } from "react";
import { getForecast, getStationForecast } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { X, AlertTriangle, ArrowUp, ArrowDown, Minus } from "lucide-react";
import Link from "next/link";

export default function ForecastPage() {
  const [data, setData] = useState<any>(null);
  const [stationData, setStationData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [isAlertModalOpen, setIsAlertModalOpen] = useState(false);

  useEffect(() => {
    Promise.all([getForecast(25), getStationForecast()]).then(([res, st]) => {
      setData(res);
      setStationData(st);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="p-12 max-w-7xl mx-auto min-h-screen flex items-center justify-center">
        <div className="text-text-secondary animate-pulse tracking-[0.2em] uppercase font-light text-sm">
          Loading predictive models...
        </div>
      </div>
    );
  }

  const forecast = data?.forecast || [];
  const topEscalations = data?.top_escalations || [];
  
  // All KPI tiles use citywide_summary (ALL hotspots, consistent scope).
  // The backend pre-computes these from the full 1196-hotspot dataset.
  const cw = data?.citywide_summary || {};
  const rising = cw.spiking ?? 0;
  const falling = cw.dropping ?? 0;
  const criticalCount = cw.critical ?? 0;
  const totalHotspots = cw.total_hotspots ?? 0;
  // Escalation detail list (for banner + modal) still from top_escalations
  const escalatingHotspots = topEscalations.filter((f: any) => f.is_escalating);

  return (
    <div className="p-12 max-w-7xl mx-auto space-y-12 bg-bg-base min-h-screen">
      <header className="space-y-4">
        <h1 className="text-5xl font-light tracking-tight text-text-primary">FORECAST</h1>
        <p className="text-text-secondary font-light text-sm tracking-wide max-w-3xl">
          {data?.predict_week_start && data?.data_through
            ? `Predicted violations for ${data.predict_week_start} – ${data.predict_week_end}, based on violation data through ${data.data_through}.`
            : "7-day predictive models for violation occurrences"}
        </p>
      </header>

      {/* KPI Cards — all citywide scope */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
        <div className="bg-transparent border border-border p-8">
          <div className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary mb-2">Forecast Week</div>
          <div className="text-4xl font-light tracking-tight">{data?.predict_week || "?"}</div>
          {data?.predict_week_start && (
            <div className="text-[10px] text-text-secondary mt-2 tracking-wide">
              {data.predict_week_start} – {data.predict_week_end}
            </div>
          )}
        </div>
        <div className="bg-transparent border border-border p-8">
          <div className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary mb-2">Forecast Accuracy</div>
          <div className="text-4xl font-light tracking-tight">{data?.model_mae?.toFixed(1) || 0}</div>
          <div className="text-[10px] text-text-secondary mt-2 tracking-wide">avg error ±{data?.model_mae?.toFixed(1) || 0} violations/hotspot/week</div>
        </div>
        <div className="bg-transparent border border-border p-8">
          <div className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary mb-2">Spiking</div>
          <div className="text-4xl font-light text-critical">{rising}</div>
          <div className="text-[10px] text-text-secondary mt-2 tracking-wide">≥10% increase · citywide ({totalHotspots})</div>
        </div>
        <div className="bg-transparent border border-border p-8">
          <div className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary mb-2">Dropping</div>
          <div className="text-4xl font-light text-patrol">{falling}</div>
          <div className="text-[10px] text-text-secondary mt-2 tracking-wide">≤-10% decrease · citywide ({totalHotspots})</div>
        </div>
        <div className="bg-transparent border border-border p-8">
          <div className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary mb-2">Critical</div>
          <div className="text-4xl font-light text-[#EF4444]">{criticalCount}</div>
          <div className="text-[10px] text-text-secondary mt-2 tracking-wide">{'>'}20% spike, baseline {'>'}15 · citywide</div>
        </div>
      </div>

      {/* Escalation Summary Banner */}
      {escalatingHotspots.length > 0 && (
        <div className="bg-[#EF4444]/10 border border-[#EF4444]/30 p-4 rounded flex items-center justify-between" id="escalation-banner">
          <div className="flex items-center gap-3">
            <AlertTriangle className="text-[#EF4444]" size={20} />
            <p className="text-sm text-[#EF4444] font-medium">
              Action Required: {escalatingHotspots.length} hotspots are predicted to surge {'>'}20%.
            </p>
          </div>
          <button 
            onClick={() => setIsAlertModalOpen(true)}
            className="text-xs uppercase tracking-wider font-bold bg-[#EF4444]/20 hover:bg-[#EF4444]/30 text-[#EF4444] px-4 py-2 rounded transition-colors"
          >
            View Alerts
          </button>
        </div>
      )}

      {/* Alert Modal */}
      {isAlertModalOpen && (
        <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-bg-surface border border-border rounded-xl w-full max-w-2xl shadow-2xl flex flex-col max-h-[80vh]">
            <div className="p-6 border-b border-border flex justify-between items-center">
              <h2 className="text-lg font-light tracking-tight text-text-primary flex items-center gap-2">
                <AlertTriangle className="text-[#EF4444]" size={20} />
                ESCALATION ALERTS
              </h2>
              <button onClick={() => setIsAlertModalOpen(false)} className="text-text-muted hover:text-text-primary transition-colors">
                <X size={20} />
              </button>
            </div>
            <div className="p-6 overflow-y-auto space-y-4">
              {escalatingHotspots.map((hs: any) => (
                <div key={hs.hotspot_id} className="bg-[#EF4444]/10 border border-[#EF4444]/30 p-4 rounded-lg flex items-start gap-3">
                  <span className="text-xl">⚠️</span>
                  <div>
                    <p className="text-sm font-medium text-[#EF4444]">Escalation Alert</p>
                    <p className="text-sm font-light text-text-primary mt-1">
                      <strong>{hs.police_station}</strong> hotspot predicted to rise <strong>{hs.change_pct}%</strong> vs baseline — consider reviewing this week's patrol assignment for <strong>{hs.hotspot_id}</strong>.
                    </p>
                  </div>
                </div>
              ))}
            </div>
            <div className="p-6 border-t border-border bg-bg-base rounded-b-xl flex justify-end gap-3">
              <Link
                href="/deploy"
                onClick={() => setIsAlertModalOpen(false)}
                className="text-sm font-medium text-text-primary bg-[#EF4444]/10 hover:bg-[#EF4444]/20 px-6 py-2 rounded transition-colors"
              >
                Go to Patrol Deployment →
              </Link>
              <button
                onClick={() => setIsAlertModalOpen(false)}
                className="text-sm font-medium text-text-primary bg-text-primary/10 hover:bg-text-primary/20 px-6 py-2 rounded transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Chart — Escalation-ranked (significant hotspots only) */}
      <div className="border border-border p-8" id="escalation-chart">
        <h2 className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary mb-1">Top 10 Escalations — Predicted vs Baseline</h2>
        <p className="text-[10px] text-text-secondary/60 mb-6 font-light">Ranked by escalation score (change % × baseline volume). Only hotspots with baseline {'>'} 15 shown.</p>
        <div className="h-[400px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={topEscalations} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2F333D" vertical={false} />
              <XAxis dataKey="hotspot_id" stroke="#9CA3AF" tick={{ fill: '#9CA3AF', fontSize: 12 }} />
              <YAxis stroke="#9CA3AF" tick={{ fill: '#9CA3AF', fontSize: 12 }} />
              <Tooltip 
                cursor={{ fill: '#22252D' }} 
                contentStyle={{ backgroundColor: '#1B1D24', borderColor: '#2F333D', color: '#F9FAFB' }}
              />
              <Legend wrapperStyle={{ paddingTop: '20px' }} />
              <Bar dataKey="predicted_count" name="Predicted (XGBoost)" fill="#6366F1" />
              <Bar dataKey="baseline_count" name="Baseline (W01-W05 avg)" fill="#374151" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Table — same data as chart (topEscalations), single source of truth */}
      <div className="border border-border overflow-hidden" id="escalation-table">
        <table className="w-full text-sm text-left">
          <thead className="text-[10px] text-text-secondary uppercase tracking-[0.2em] font-medium border-b border-border bg-text-primary/5">
            <tr>
              <th className="px-6 py-6">Hotspot</th>
              <th className="px-6 py-6">Station</th>
              <th className="px-6 py-6 text-right">Predicted</th>
              <th className="px-6 py-6 text-right">Baseline</th>
              <th className="px-6 py-6 text-right">Delta</th>
              <th className="px-6 py-6 text-right">Change vs 5-wk avg</th>
              <th className="px-6 py-6 text-center">Status</th>
              <th className="px-6 py-6" title="The model's top reason this hotspot is forecast to spike — based on its recent trend, surrounding cluster, and seasonal patterns">Why it&apos;s rising</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {topEscalations.map((row: any) => (
              <tr key={row.hotspot_id} className={`hover:bg-text-primary/5 transition-colors ${row.is_escalating ? 'bg-[#EF4444]/5' : ''}`}>
                <td className="px-6 py-6 font-light text-text-primary">{row.hotspot_id}</td>
                <td className="px-6 py-6 text-text-secondary">{row.police_station}</td>
                <td className="px-6 py-6 text-right font-light text-text-primary">{row.predicted_count?.toFixed(1)}</td>
                <td className="px-6 py-6 text-right font-light text-text-secondary">{row.baseline_count}</td>
                <td className={`px-6 py-6 text-right font-light ${(row.count_delta ?? 0) > 0 ? 'text-critical' : 'text-patrol'}`}>
                  {(row.count_delta ?? 0) > 0 ? '+' : ''}{row.count_delta ?? 0}
                </td>
                <td className={`px-6 py-6 text-right font-light ${row.change_pct > 0 ? 'text-critical' : 'text-patrol'}`}>
                  {row.change_pct != null ? `${row.change_pct > 0 ? '+' : ''}${row.change_pct?.toFixed(1)}%` : '\u2014'}
                </td>
                <td className="px-6 py-6 text-center">
                  {row.is_escalating ? (
                    <span className="text-[10px] uppercase tracking-wider font-bold text-[#EF4444] bg-[#EF4444]/10 px-2 py-1 rounded">Critical</span>
                  ) : row.trend_label === 'rising' ? (
                    <span className="text-[10px] uppercase tracking-wider font-medium text-amber-400 bg-amber-400/10 px-2 py-1 rounded">Rising</span>
                  ) : row.trend_label === 'declining' ? (
                    <span className="text-[10px] uppercase tracking-wider font-medium text-patrol bg-patrol/10 px-2 py-1 rounded">Declining</span>
                  ) : (
                    <span className="text-[10px] uppercase tracking-wider font-medium text-text-secondary bg-text-primary/5 px-2 py-1 rounded">Stable</span>
                  )}
                </td>
                <td className="px-6 py-6">
                  <div className="flex flex-wrap gap-1.5">
                    {(row.top_reasons || []).map((r: any, i: number) => (
                      <span
                        key={i}
                        className={`inline-flex items-center gap-1 text-[10px] px-2 py-1 rounded tracking-wide font-light ${
                          r.direction === 'up'
                            ? 'text-critical bg-critical/10'
                            : 'text-text-muted bg-text-primary/5'
                        }`}
                      >
                        {r.label}
                        <span className="font-medium">{r.direction === 'up' ? '\u2191' : '\u2193'}</span>
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-[10px] text-text-secondary font-light tracking-wide -mt-8">
        ↑ = factor pushing violations higher this week · ↓ = factor stabilising the hotspot · Factors are the model&apos;s top drivers from historical patterns.
      </p>

      {/* Full Volume-Ranked List (expandable) */}
      <details className="border border-border">
        <summary className="px-8 py-6 cursor-pointer text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary hover:text-text-primary transition-colors">
          All Hotspots by Volume ({forecast.length} total)
        </summary>
        <div className="overflow-hidden">
          <table className="w-full text-sm text-left">
            <thead className="text-[10px] text-text-secondary uppercase tracking-[0.2em] font-medium border-b border-border bg-text-primary/5">
              <tr>
                <th className="px-6 py-4">Hotspot</th>
                <th className="px-6 py-4">Station</th>
                <th className="px-6 py-4 text-right">Predicted</th>
                <th className="px-6 py-4 text-right">Baseline</th>
                <th className="px-6 py-4 text-right">Delta</th>
                <th className="px-6 py-4 text-right">Change</th>
                <th className="px-6 py-4 text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {forecast.map((row: any) => (
                <tr key={row.hotspot_id} className="hover:bg-text-primary/5 transition-colors">
                  <td className="px-6 py-4 font-light text-text-primary">{row.hotspot_id}</td>
                  <td className="px-6 py-4 text-text-secondary">{row.police_station}</td>
                  <td className="px-6 py-4 text-right font-light text-text-primary">{row.predicted_count?.toFixed(1)}</td>
                  <td className="px-6 py-4 text-right font-light text-text-secondary">{row.baseline_count}</td>
                  <td className={`px-6 py-4 text-right font-light ${(row.count_delta ?? 0) > 0 ? 'text-critical' : 'text-patrol'}`}>
                    {(row.count_delta ?? 0) > 0 ? '+' : ''}{row.count_delta ?? 0}
                  </td>
                  <td className={`px-6 py-4 text-right font-light ${row.change_pct > 0 ? 'text-critical' : 'text-patrol'}`}>
                    {row.change_pct != null ? `${row.change_pct > 0 ? '+' : ''}${row.change_pct?.toFixed(1)}%` : '\u2014'}
                  </td>
                  <td className="px-6 py-4 text-center">
                    {row.is_escalating ? (
                      <span className="text-[10px] uppercase tracking-wider font-bold text-[#EF4444] bg-[#EF4444]/10 px-2 py-1 rounded">Critical</span>
                    ) : row.trend_label === 'rising' ? (
                      <span className="text-[10px] uppercase tracking-wider font-medium text-amber-400 bg-amber-400/10 px-2 py-1 rounded">Rising</span>
                    ) : row.trend_label === 'declining' ? (
                      <span className="text-[10px] uppercase tracking-wider font-medium text-patrol bg-patrol/10 px-2 py-1 rounded">Declining</span>
                    ) : (
                      <span className="text-[10px] uppercase tracking-wider font-medium text-text-secondary bg-text-primary/5 px-2 py-1 rounded">Stable</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      {/* ── Station-level forecast ─────────────────────────────────────────── */}
      {/* Coarser grain than per-hotspot → law of large numbers → far more       */}
      {/* predictable. Framed as the deliberate design choice behind pairing the */}
      {/* noisy per-hotspot forecast with the escalation watch.                  */}
      {stationData && (
        <section className="space-y-6 pt-8 border-t border-border" id="station-forecast">
          <header className="space-y-2">
            <h2 className="text-2xl font-light tracking-tight text-text-primary">STATION-LEVEL FORECAST</h2>
            <p className="text-text-secondary font-light text-sm tracking-wide max-w-3xl">
              Aggregating to {stationData.n_stations} police stations smooths out per-hotspot
              noise. We forecast station trends accurately, and pair the noisier per-hotspot
              forecast above with the escalation watch — rather than chasing exact per-hotspot counts.
            </p>
          </header>

          {/* 3-card accuracy strip — each card shows the station-vs-hotspot contrast */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Card 1 — ranking accuracy: station P@10 vs hotspot P@10 */}
            <div className="bg-transparent border border-border p-8">
              <div className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary mb-3">Top-10 Ranking Accuracy</div>
              <div className="flex items-baseline gap-3">
                <span className="text-4xl font-light tracking-tight text-patrol">
                  {stationData.precision_at?.[10] != null ? `${(stationData.precision_at[10] * 100).toFixed(0)}%` : "—"}
                </span>
                <span className="text-sm font-light text-text-secondary">station</span>
                <span className="text-text-muted">vs</span>
                <span className="text-2xl font-light tracking-tight text-critical">
                  {stationData.hotspot_precision_at?.[10] != null ? `${(stationData.hotspot_precision_at[10] * 100).toFixed(0)}%` : "—"}
                </span>
                <span className="text-sm font-light text-text-secondary">hotspot</span>
              </div>
              <div className="text-[10px] text-text-secondary mt-3 tracking-wide">8 in 10 top-ranked stations are genuinely high-risk — reliable for shift planning</div>
            </div>

            {/* Card 2 — noise: station CV vs hotspot CV */}
            <div className="bg-transparent border border-border p-8">
              <div className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary mb-3">Forecast Stability</div>
              <div className="flex items-baseline gap-3">
                <span className="text-4xl font-light tracking-tight text-patrol">{stationData.median_cv?.toFixed(2)}</span>
                <span className="text-sm font-light text-text-secondary">station</span>
                <span className="text-text-muted">vs</span>
                <span className="text-2xl font-light tracking-tight text-critical">{stationData.hotspot_median_cv?.toFixed(2)}</span>
                <span className="text-sm font-light text-text-secondary">hotspot</span>
              </div>
              <div className="text-[10px] text-text-secondary mt-3 tracking-wide">Station counts swing ±{stationData.median_cv != null ? (stationData.median_cv * 100).toFixed(0) : "—"}% week-to-week vs ±{stationData.hotspot_median_cv != null ? (stationData.hotspot_median_cv * 100).toFixed(0) : "—"}% at hotspot level — far more stable for planning</div>
            </div>

            {/* Card 3 — the design-choice caption */}
            <div className="bg-text-primary/[0.03] border border-border p-8 flex flex-col justify-center">
              <div className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary mb-3">Why Two Grains</div>
              <p className="text-sm font-light text-text-primary leading-relaxed">
                Per-hotspot counts are irreducibly noisy. We forecast <span className="text-patrol">station trends accurately</span> and
                pair the noisier per-hotspot view with the <span className="text-text-primary">escalation watch</span> — rather than
                chasing exact per-hotspot counts.
              </p>
            </div>
          </div>

          {/* Station table — ranked by predicted count */}
          <div className="border border-border overflow-hidden" id="station-forecast-table">
            <table className="w-full text-sm text-left">
              <thead className="text-[10px] text-text-secondary uppercase tracking-[0.2em] font-medium border-b border-border bg-text-primary/5">
                <tr>
                  <th className="px-6 py-6">Station</th>
                  <th className="px-6 py-6 text-right">Predicted</th>
                  <th className="px-6 py-6 text-right">Baseline</th>
                  <th className="px-6 py-6 text-right">Change vs baseline</th>
                  <th className="px-6 py-6 text-center">Trend</th>
                  <th className="px-6 py-6">Peak Shifts</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(stationData.forecast || []).map((row: any) => (
                  <tr key={row.police_station} className="hover:bg-text-primary/5 transition-colors">
                    <td className="px-6 py-6 font-light text-text-primary">{row.police_station}</td>
                    <td className="px-6 py-6 text-right font-light text-text-primary">{row.predicted_count?.toFixed(1)}</td>
                    <td className="px-6 py-6 text-right font-light text-text-secondary">{row.baseline_count?.toFixed(1)}</td>
                    <td className={`px-6 py-6 text-right font-light ${row.change_pct > 0 ? 'text-critical' : 'text-patrol'}`}>
                      {row.change_pct != null ? `${row.change_pct > 0 ? '+' : ''}${row.change_pct?.toFixed(1)}%` : '—'}
                    </td>
                    <td className="px-6 py-6">
                      <div className="flex items-center justify-center gap-1.5">
                        {row.trend_label === 'rising' ? (
                          <><ArrowUp size={14} className="text-amber-400" /><span className="text-[10px] uppercase tracking-wider font-medium text-amber-400">Rising</span></>
                        ) : row.trend_label === 'declining' ? (
                          <><ArrowDown size={14} className="text-patrol" /><span className="text-[10px] uppercase tracking-wider font-medium text-patrol">Declining</span></>
                        ) : (
                          <><Minus size={14} className="text-text-secondary" /><span className="text-[10px] uppercase tracking-wider font-medium text-text-secondary">Stable</span></>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-6">
                      <div className="flex flex-col gap-1">
                        {(row.peak_shifts || []).map((ps: any, i: number) => (
                          <span key={i} className="text-[10px] font-light text-text-secondary tracking-wide">
                            <span className="text-text-primary">{ps.day} {ps.shift}</span>
                            <span className="text-text-muted ml-1">{ps.pct}%</span>
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
