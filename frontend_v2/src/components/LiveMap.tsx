"use client";

import { useEffect, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";

const TIER_COLORS: Record<string, string> = {
  Critical: "#EF4444",
  Elevated: "#F59E0B",
  Standard: "#3B82F6",
};

export default function LiveMap({ hotspots, assignments = [] }: { hotspots: any[], assignments?: string[] }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return <div className="h-[600px] w-full bg-bg-surface animate-pulse rounded-xl border border-border flex items-center justify-center text-text-muted">Loading map...</div>;

  const allScores = [...hotspots].map(h => h.risk_score).sort((a, b) => a - b);
  const p90 = allScores[Math.floor(allScores.length * 0.9)] || 50;
  const p99 = allScores[Math.floor(allScores.length * 0.99)] || 60;

  function getTier(score: number) {
    if (score >= p99) return "Critical";
    if (score >= p90) return "Elevated";
    return "Standard";
  }

  return (
    <div className="h-full w-full overflow-hidden relative z-0 rounded-2xl border border-border">
      <MapContainer
        center={[12.9716, 77.5946]}
        zoom={12}
        className="w-full h-full z-0"
        zoomControl={false}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
        />
        {hotspots.map((hs) => {
          const tier = getTier(hs.risk_score);
          const color = TIER_COLORS[tier];
          const radius = Math.max(5, hs.risk_score / 8);
          const isAssigned = assignments.includes(hs.hotspot_id);

          return (
            <div key={hs.hotspot_id}>
              <CircleMarker
                center={[hs.lat, hs.lng]}
                pathOptions={{
                  color: color,
                  fillColor: color,
                  fillOpacity: 0.8,
                  weight: 1,
                }}
                radius={radius}
              >
              <Popup className="custom-popup">
                <div className="text-sm font-sans min-w-[150px] text-text-primary">
                  <div className="font-light text-xl tracking-tight mb-1">{hs.hotspot_id}</div>
                  <div className={`inline-block px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider mb-3
                    ${tier === 'Critical' ? 'bg-red-900/40 text-red-300 border border-red-500/50' : 
                      tier === 'Elevated' ? 'bg-amber-900/40 text-amber-300 border border-amber-500/50' : 
                      'bg-blue-900/40 text-blue-300 border border-blue-500/50'}`}
                  >
                    {tier}
                  </div>
                  <div className="flex justify-between border-t border-border pt-2 mb-1">
                    <span className="text-text-secondary text-[10px] uppercase tracking-[0.2em]">Risk</span>
                    <span className="font-light text-text-primary">{hs.risk_score?.toFixed(1)}</span>
                  </div>
                  <div className="flex justify-between mb-1">
                    <span className="text-text-secondary text-[10px] uppercase tracking-[0.2em]">Vio</span>
                    <span className="font-light text-text-primary">{hs.violation_count}</span>
                  </div>
                  <div className="flex justify-between pb-1">
                    <span className="text-text-secondary text-[10px] uppercase tracking-[0.2em]">Win</span>
                    <span className="font-light text-text-primary">{hs.logging_window}</span>
                  </div>
                  {isAssigned && (
                    <div className="mt-2 border-t border-border pt-2">
                      <span className="inline-block px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider bg-emerald-900/40 text-emerald-400 border border-emerald-500/50">
                        Patrol Assigned
                      </span>
                    </div>
                  )}
                </div>
              </Popup>
            </CircleMarker>
            {isAssigned && (
              <CircleMarker
                center={[hs.lat, hs.lng]}
                pathOptions={{
                  color: "#10B981",
                  fillColor: "transparent",
                  fillOpacity: 0,
                  weight: 4,
                  dashArray: "6 6",
                }}
                radius={radius + 6}
              />
            )}
            </div>
          );
        })}
      </MapContainer>
      
      {/* Legend */}
      <div className="absolute bottom-6 right-6 bg-black/80 backdrop-blur border border-border p-4 z-[1000]">
        <div className="text-[10px] font-bold text-text-secondary uppercase tracking-[0.2em] mb-4">Risk Tier</div>
        <div className="flex items-center gap-3 mb-3 text-[10px] tracking-widest font-medium text-text-primary">
          <span className="w-3 h-3 rounded-full bg-[#EF4444]"></span> CRITICAL
        </div>
        <div className="flex items-center gap-3 mb-3 text-[10px] tracking-widest font-medium text-text-primary">
          <span className="w-3 h-3 rounded-full bg-[#F59E0B]"></span> ELEVATED
        </div>
        <div className="flex items-center gap-3 text-[10px] tracking-widest font-medium text-text-primary">
          <span className="w-3 h-3 rounded-full bg-[#3B82F6]"></span> STANDARD
        </div>
      </div>
    </div>
  );
}
