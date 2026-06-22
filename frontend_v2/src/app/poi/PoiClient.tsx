"use client";

import { useState } from "react";
import MapWrapper from "@/components/MapWrapper";
import { Train } from "lucide-react";

export default function PoiClient({ stats, hotspots }: { stats: any[]; hotspots: any[] }) {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const metroCategory = stats.find((c) => c.poi_category === "metro");
  const totalViolations = stats.reduce((sum, c) => sum + c.total_violations, 0);
  const metroShare =
    metroCategory && totalViolations > 0
      ? ((metroCategory.total_violations / totalViolations) * 100).toFixed(1)
      : null;

  return (
    <div className="flex h-screen bg-bg-base overflow-hidden">
      {/* Left Column: Table */}
      <div className="w-[450px] shrink-0 border-r border-border flex flex-col h-full z-10 bg-bg-base relative shadow-2xl overflow-y-auto">
        <div className="p-8">
          <header className="space-y-4 mb-8">
            <h1 className="text-4xl font-light tracking-tight text-text-primary">POI SPILLOVER</h1>
            <p className="text-text-secondary font-light text-xs tracking-wide leading-relaxed">
              Analysis of parking violations around major Points of Interest. Click a category to highlight tagged hotspots on the map.
            </p>
          </header>

          {metroShare !== null && (
            <div className="bg-transparent border border-border p-6 mb-8">
              <div className="flex items-center justify-between mb-6">
                <div className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary">
                  Metro Spillover
                </div>
                <Train size={14} className="text-text-primary" strokeWidth={1} />
              </div>
              <div className="text-4xl font-light text-text-primary tracking-tight">
                {metroShare}%
              </div>
              <div className="text-[10px] text-text-secondary mt-2 tracking-wide">
                of tagged violations at metro-proximate hotspots
              </div>
            </div>
          )}

          <div className="border border-border overflow-hidden">
            <table className="w-full text-sm text-left">
              <thead className="text-[10px] text-text-secondary uppercase tracking-[0.2em] font-medium border-b border-border bg-text-primary/5">
                <tr>
                  <th className="px-4 py-4">Category</th>
                  <th className="px-4 py-4 text-right">Hotspots</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {stats.map((row: any, i: number) => {
                  const isSelected = selectedCategory === row.poi_category;
                  return (
                    <tr 
                      key={i} 
                      onClick={() => setSelectedCategory(isSelected ? null : row.poi_category)}
                      className={`cursor-pointer transition-colors ${isSelected ? 'bg-text-primary/10 border-l-2 border-l-fuchsia-500' : 'hover:bg-text-primary/5 border-l-2 border-l-transparent'}`}
                    >
                      <td className="px-4 py-4 font-light text-text-primary capitalize">{row.poi_category}</td>
                      <td className="px-4 py-4 text-right font-light text-text-primary">{row.hotspot_count}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          
          {selectedCategory && (
            <div className="mt-8 p-4 border border-fuchsia-500/30 bg-fuchsia-900/10 text-xs text-text-secondary">
              Viewing <span className="text-fuchsia-400 font-bold uppercase">{selectedCategory}</span> hotspots. Map markers are highlighted in fuchsia.
            </div>
          )}
        </div>
      </div>

      {/* Right Column: Map */}
      <div className="flex-1 h-full relative p-8 pl-0">
        <MapWrapper hotspots={hotspots} highlightPoi={selectedCategory} />
      </div>
    </div>
  );
}
