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
      });
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
          <h1 className="text-5xl font-light tracking-tight text-text-primary">TEMPORAL DIST</h1>
          <p className="text-text-secondary font-light text-sm tracking-wide">
            Violation counts by hour and weekday for specific hotspots
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

      <div className="border border-border p-8 overflow-x-auto relative">
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
    </div>
  );
}
