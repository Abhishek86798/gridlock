"use client";

import { useEffect, useState } from "react";
import { getHotspots } from "@/lib/api";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export default function TemporalPage() {
  const [hotspots, setHotspots] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [matrix, setMatrix] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getHotspots({ limit: 500 }).then((res) => {
      setHotspots(res);
      if (res.length > 0) {
        setSelectedId(res[0].hotspot_id);
      }
    });
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setLoading(true);
    fetch(`${BASE_URL}/temporal/${selectedId}`)
      .then(res => res.json())
      .then(data => {
        setMatrix(data.matrix || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [selectedId]);

  // Pivot the matrix [hour][day_of_week]
  const heatMap = Array.from({ length: 24 }, () => Array(7).fill(0));
  let maxCount = 1;

  matrix.forEach((cell) => {
    heatMap[cell.hour][cell.day_of_week] = cell.count;
    if (cell.count > maxCount) maxCount = cell.count;
  });

  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  return (
    <div className="p-12 max-w-7xl mx-auto space-y-12 bg-bg-base min-h-screen">
      <header className="flex justify-between items-end">
        <div className="space-y-4">
          <h1 className="text-5xl font-light tracking-tight text-text-primary">VIOLATION TIMING</h1>
          <p className="text-text-secondary font-light text-sm tracking-wide max-w-lg">
            Select a hotspot to see which hours and days see the most violations. Darker red = more violations. Use this to set patrol shift times.
          </p>
        </div>
        <div className="border border-border px-6 py-4 flex items-center gap-6">
          <label className="text-[10px] font-medium uppercase tracking-[0.2em] text-text-secondary">Select Hotspot</label>
          <select 
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value)}
            className="bg-transparent border border-border rounded-none px-4 py-2 text-xs font-light text-text-primary focus:outline-none focus:border-text-secondary appearance-none"
          >
            {hotspots.map(h => (
              <option key={h.hotspot_id} value={h.hotspot_id} className="bg-black text-text-primary">
                {h.hotspot_id}
              </option>
            ))}
          </select>
        </div>
      </header>

      {/* Peak window callout */}
      {matrix.length > 0 && (() => {
        const sorted = [...matrix].sort((a, b) => b.count - a.count).slice(0, 3);
        const dayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
        return (
          <div className="flex items-center gap-4 flex-wrap">
            <span className="text-[10px] text-text-secondary uppercase tracking-widest shrink-0">Peak windows:</span>
            {sorted.map((c, i) => (
              <span key={i} className="text-[10px] font-light text-critical bg-critical/10 px-3 py-1">
                {dayNames[c.day_of_week]} {c.hour.toString().padStart(2, '0')}:00–{(c.hour + 1).toString().padStart(2, '0')}:00
              </span>
            ))}
          </div>
        );
      })()}

      <div className="border border-border p-8 overflow-x-auto relative">
        {/* Color scale legend */}
        <div className="flex items-center gap-3 mb-6 text-[10px] text-text-secondary">
          <span>Fewer violations</span>
          <div className="flex gap-0.5">
            {[0.1, 0.3, 0.5, 0.7, 0.9].map(v => (
              <div key={v} className="w-6 h-4" style={{ backgroundColor: `rgba(239,68,68,${v * 0.8})` }} />
            ))}
          </div>
          <span>More violations</span>
        </div>

        {loading && (
          <div className="absolute inset-0 bg-bg-base/80 backdrop-blur-sm flex items-center justify-center z-10">
            <span className="text-text-muted animate-pulse font-light tracking-[0.2em] uppercase text-[10px]">Loading Data...</span>
          </div>
        )}
        
        <table className="w-full text-xs text-center border-collapse">
          <thead>
            <tr>
              <th className="p-4 border border-border font-light text-text-secondary uppercase tracking-[0.2em] text-[10px]">Hour</th>
              {days.map(d => (
                <th key={d} className="p-4 border border-border font-light uppercase tracking-[0.2em] text-text-secondary text-[10px]">{d}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {heatMap.map((row, hour) => (
              <tr key={hour}>
                <td className="p-4 border border-border font-light text-text-secondary">
                  {hour.toString().padStart(2, '0')}:00
                </td>
                {row.map((val, day) => {
                  const intensity = Math.min(1, val / maxCount);
                  // Heatmap color logic
                  const bg = val > 0 ? `rgba(239, 68, 68, ${Math.max(0.1, intensity * 0.8)})` : 'transparent'; 
                  const text = val > 0 ? '#ffffff' : '#525252';
                  
                  return (
                    <td key={day} className="p-4 border border-border font-light transition-colors" style={{ backgroundColor: bg, color: text }}>
                      {val > 0 ? val : '-'}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[10px] text-text-secondary font-light tracking-wide">
        Use peak hours from this hotspot to time patrol shifts on the Patrol Deployment page.
      </p>
    </div>
  );
}
