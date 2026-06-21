"use client";

import { useEffect, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, Polyline, useMap } from "react-leaflet";
import { Search, LocateFixed } from "lucide-react";
import "leaflet/dist/leaflet.css";
import { useWatchlist } from "@/lib/hooks/useWatchlist";

const TIER_COLORS: Record<string, string> = {
  Critical: "#EF4444",
  Elevated: "#F59E0B",
  Standard: "#3B82F6",
};

// Child component to handle programmatic map flying
function MapController({ flyConfig }: { flyConfig: { target: [number, number], zoom: number } | null }) {
  const map = useMap();
  useEffect(() => {
    if (flyConfig) {
      map.flyTo(flyConfig.target, flyConfig.zoom, { duration: 1.5 });
    }
  }, [flyConfig, map]);
  return null;
}

// Child component to handle dynamic grid panning and zooming
function DynamicGridOverlay() {
  const map = useMap();
  const [transform, setTransform] = useState({ scale: 1, x: 0, y: 0 });

  useEffect(() => {
    const update = () => {
      const zoom = map.getZoom();
      const scale = Math.pow(2, zoom - 12); // Base zoom level is 12
      const bounds = map.getPixelBounds();
      if (!bounds?.min) return;
      setTransform({ scale, x: -bounds.min.x, y: -bounds.min.y });
    };
    
    map.on('move', update);
    map.on('zoom', update);
    update(); // Initial calculation
    
    return () => { 
      map.off('move', update);
      map.off('zoom', update);
    };
  }, [map]);

  const size = 60 * transform.scale;

  return (
    <div 
      className="absolute inset-0 z-[500] pointer-events-none"
      style={{
        backgroundSize: `${size}px ${size}px`,
        backgroundPosition: `${transform.x}px ${transform.y}px`,
        backgroundImage: 'linear-gradient(to right, rgba(255, 255, 255, 0.08) 1px, transparent 1px), linear-gradient(to bottom, rgba(255, 255, 255, 0.08) 1px, transparent 1px)'
      }}
    />
  );
}

export default function LiveMap({ hotspots, assignments = [], highlightPoi }: { hotspots: any[], assignments?: any[], highlightPoi?: string | null }) {
  const [mounted, setMounted] = useState(false);
  const { watchlist } = useWatchlist();
  const [searchQuery, setSearchQuery] = useState("");
  const [flyConfig, setFlyConfig] = useState<{ target: [number, number], zoom: number } | null>(null);
  const [highlightedSearchId, setHighlightedSearchId] = useState<string | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    const found = hotspots.find(hs => hs.hotspot_id.toLowerCase() === searchQuery.trim().toLowerCase());
    if (found) {
      setFlyConfig({ target: [found.lat, found.lng], zoom: 16 });
      setHighlightedSearchId(found.hotspot_id);
    } else {
      alert(`Hotspot ${searchQuery} not found on this map.`);
    }
  };

  if (!mounted) return <div className="h-[600px] w-full bg-bg-surface animate-pulse rounded-xl border border-border flex items-center justify-center text-text-muted">Loading map...</div>;

  const allScores = [...hotspots].map(h => h.risk_score).sort((a, b) => a - b);
  const p90 = allScores[Math.floor(allScores.length * 0.9)] || 50;
  const p99 = allScores[Math.floor(allScores.length * 0.99)] || 60;

  function getTier(score: number) {
    if (score >= p99) return "Critical";
    if (score >= p90) return "Elevated";
    return "Standard";
  }

  // Pre-compute all hotspot IDs that are part of ANY route
  const assignedHotspotIds = new Set<string>();
  assignments.forEach((a) => {
    if (a.route) {
      a.route.forEach((id: string) => assignedHotspotIds.add(id));
    } else if (a.hotspot_id) {
      assignedHotspotIds.add(a.hotspot_id);
    }
  });

  return (
    <div className="h-full w-full overflow-hidden relative z-0 rounded-2xl border border-border">
      <MapContainer
        center={[12.9716, 77.5946]}
        zoom={12}
        className="w-full h-full z-0"
        zoomControl={false}
      >
        <DynamicGridOverlay />
        <MapController flyConfig={flyConfig} />
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
        />
        {hotspots.map((hs) => {
          const tier = getTier(hs.risk_score);
          let color = TIER_COLORS[tier];
          let fillOpacity = 0.8;
          let weight = 1;
          let radius = Math.max(5, hs.risk_score / 8);

          const isAssigned = assignedHotspotIds.has(hs.hotspot_id);
          const isPinned = watchlist.includes(hs.hotspot_id);
          const isSearched = highlightedSearchId === hs.hotspot_id;

          // Apply POI highlighting logic if a category is selected
          if (highlightPoi) {
            if (hs.poi_category === highlightPoi) {
              color = "#D946EF"; // Vibrant Fuchsia
              fillOpacity = 0.9;
              radius = radius + 2;
              weight = 2;
            } else {
              color = "#374151"; // Faded gray for non-matches
              fillOpacity = 0.2;
              weight = 0;
            }
          }
          
          // Watchlist pinning takes higher visual priority
          if (isPinned && !highlightPoi) {
            color = "#06B6D4"; // Cyan
            fillOpacity = 1;
            radius = radius + 4;
            weight = 3;
          }
          
          // Searched hotspot takes the absolute highest visual priority
          if (isSearched) {
            color = "#F5F5DC"; // Beige
            fillOpacity = 1;
            radius = radius + 6; // Make it extra large
            weight = 4; // Thick border
          }

          return (
            <div key={hs.hotspot_id}>
              <CircleMarker
                center={[hs.lat, hs.lng]}
                pathOptions={{
                  color: isSearched ? "#FFFFFF" : ((highlightPoi && hs.poi_category === highlightPoi) ? "#F0ABFC" : (isPinned && !highlightPoi ? "#67E8F9" : color)), 
                  fillColor: color,
                  fillOpacity: fillOpacity,
                  weight: weight,
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
                  {hs.poi_category && (
                    <div className="flex justify-between pb-1 border-t border-border pt-1 mt-1">
                      <span className="text-text-secondary text-[10px] uppercase tracking-[0.2em]">POI</span>
                      <span className="font-medium text-fuchsia-400 capitalize">{hs.poi_category}</span>
                    </div>
                  )}
                  {isAssigned && (
                    <div className="mt-2 border-t border-border pt-2">
                      <span className="inline-block px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider bg-emerald-900/40 text-emerald-400 border border-emerald-500/50">
                        Patrol Assigned
                      </span>
                    </div>
                  )}
                  {isPinned && (
                    <div className="mt-2 border-t border-border pt-2">
                      <span className="inline-block px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider bg-cyan-900/40 text-cyan-400 border border-cyan-500/50">
                        Pinned from Repeat Offenders
                      </span>
                    </div>
                  )}
                  {isSearched && (
                    <div className="mt-2 border-t border-border pt-2">
                      <span className="inline-block px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider bg-[#F5F5DC]/20 text-[#F5F5DC] border border-[#F5F5DC]/50">
                        Searched Result
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

        {/* Draw Patrol Routes */}
        {assignments.map((assignment, idx) => {
          if (!assignment.route_geometry || assignment.route_geometry.length < 2) return null;
          return (
            <Polyline
              key={`route-${idx}`}
              positions={assignment.route_geometry}
              pathOptions={{
                color: "#10B981", // Patrol green
                weight: 4,
                opacity: 0.8,
                dashArray: "8 8",
              }}
            />
          );
        })}
      </MapContainer>
      
      {/* Search Bar & Recenter Overlay */}
      <div className="absolute top-6 left-6 z-[1000] flex gap-2">
        <form onSubmit={handleSearch} className="flex items-center bg-black/80 backdrop-blur border border-border p-2 rounded shadow-2xl transition-all focus-within:border-text-primary/30">
          <Search size={16} className="text-text-secondary ml-2 mr-3" />
          <input
            type="text"
            placeholder="Search Hotspot (e.g. HS-0064)"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="bg-transparent border-none outline-none text-sm font-light text-text-primary placeholder:text-text-muted w-[240px]"
          />
        </form>
        <button 
          onClick={() => {
            setFlyConfig({ target: [12.9716, 77.5946], zoom: 12 });
            setHighlightedSearchId(null);
            setSearchQuery("");
          }}
          className="bg-black/80 backdrop-blur border border-border px-4 py-2 rounded shadow-2xl flex items-center justify-center hover:bg-text-primary/10 transition-colors text-text-secondary hover:text-text-primary"
          title="Recenter Map"
        >
          <LocateFixed size={18} />
        </button>
      </div>

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
