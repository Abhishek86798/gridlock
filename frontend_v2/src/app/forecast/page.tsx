"use client";

import { useEffect, useState } from "react";
import { getForecast } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";

export default function ForecastPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getForecast(25).then((res) => {
      setData(res);
      setLoading(false);
    });
  }, []);

  if (loading) return <div className="p-8 text-text-muted animate-pulse">Loading predictive models...</div>;

  const forecast = data?.forecast || [];
  const top10 = forecast.slice(0, 10);
  
  const rising = forecast.filter((f: any) => f.change_pct > 10).length;
  const falling = forecast.filter((f: any) => f.change_pct < -10).length;

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

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
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
          <div className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary mb-2">Model MAE</div>
          <div className="text-4xl font-light tracking-tight">{data?.model_mae?.toFixed(1) || 0}</div>
          <div className="text-[10px] text-text-secondary mt-2 tracking-wide">violations / hotspot</div>
        </div>
        <div className="bg-transparent border border-border p-8">
          <div className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary mb-2">Spiking</div>
          <div className="text-4xl font-light text-critical">{rising}</div>
          <div className="text-[10px] text-text-secondary mt-2 tracking-wide">≥10% increase</div>
        </div>
        <div className="bg-transparent border border-border p-8">
          <div className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary mb-2">Dropping</div>
          <div className="text-4xl font-light text-patrol">{falling}</div>
          <div className="text-[10px] text-text-secondary mt-2 tracking-wide">≤-10% decrease</div>
        </div>
      </div>

      {/* Chart */}
      <div className="border border-border p-8">
        <h2 className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary mb-6">Top 10 - Predicted vs Baseline</h2>
        <div className="h-[400px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={top10} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2F333D" vertical={false} />
              <XAxis dataKey="hotspot_id" stroke="#9CA3AF" tick={{ fill: '#9CA3AF', fontSize: 12 }} />
              <YAxis stroke="#9CA3AF" tick={{ fill: '#9CA3AF', fontSize: 12 }} />
              <Tooltip 
                cursor={{ fill: '#22252D' }} 
                contentStyle={{ backgroundColor: '#1B1D24', borderColor: '#2F333D', color: '#F9FAFB' }}
              />
              <Legend wrapperStyle={{ paddingTop: '20px' }} />
              <Bar dataKey="predicted_count" name="Predicted" fill="#6366F1" />
              <Bar dataKey="baseline_count" name="Baseline (8w)" fill="#374151" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Table */}
      <div className="border border-border overflow-hidden">
        <table className="w-full text-sm text-left">
          <thead className="text-[10px] text-text-secondary uppercase tracking-[0.2em] font-medium border-b border-border bg-text-primary/5">
            <tr>
              <th className="px-8 py-6">Hotspot</th>
              <th className="px-8 py-6">Station</th>
              <th className="px-8 py-6 text-right">Predicted</th>
              <th className="px-8 py-6 text-right">Baseline</th>
              <th className="px-8 py-6 text-right">Change</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {forecast.map((row: any) => (
              <tr key={row.hotspot_id} className="hover:bg-text-primary/5 transition-colors">
                <td className="px-8 py-6 font-light text-text-primary">{row.hotspot_id}</td>
                <td className="px-8 py-6 text-text-secondary">{row.police_station}</td>
                <td className="px-8 py-6 text-right font-light text-text-primary">{row.predicted_count?.toFixed(1)}</td>
                <td className="px-8 py-6 text-right font-light text-text-secondary">{row.baseline_count?.toFixed(0)}</td>
                <td className={`px-8 py-6 text-right font-light ${row.change_pct > 0 ? 'text-critical' : 'text-patrol'}`}>
                  {row.change_pct > 0 ? '+' : ''}{row.change_pct?.toFixed(1)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
