"use client";

import { useState } from "react";
import MapWrapper from "@/components/MapWrapper";
import { Train, Building2, AlertTriangle, Bus, MapPin } from "lucide-react";

export default function PoiClient({ stats, hotspots }: { stats: any[]; hotspots: any[] }) {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const activeCategoryStr = selectedCategory || "metro";
  const activeCategory = stats.find((c) => c.poi_category === activeCategoryStr);
  const totalViolations = stats.reduce((sum, c) => sum + c.total_violations, 0);
  const activeShare =
    activeCategory && totalViolations > 0
      ? ((activeCategory.total_violations / totalViolations) * 100).toFixed(1)
      : null;

  const getCategoryTitle = (cat: string) => {
    switch (cat) {
      case "metro": return "Metro Station Effect";
      case "commercial": return "Commercial Center Effect";
      case "sensitive": return "Sensitive Area Effect";
      case "transit": return "Transit Hub Effect";
      default: return `${cat} Effect`;
    }
  };

  const getCategorySubtitle = (cat: string) => {
    switch (cat) {
      case "metro": return "of all violations occur within 500m of a metro station";
      case "commercial": return "of all violations occur near commercial centers";
      case "sensitive": return "of all violations occur near schools or hospitals";
      case "transit": return "of all violations occur near bus stops or transit hubs";
      default: return `of all violations occur near ${cat} locations`;
    }
  };

  const CategoryIcon = ({ cat }: { cat: string }) => {
    switch (cat) {
      case "metro": return <Train size={14} className="text-text-primary" strokeWidth={1} />;
      case "commercial": return <Building2 size={14} className="text-text-primary" strokeWidth={1} />;
      case "sensitive": return <AlertTriangle size={14} className="text-text-primary" strokeWidth={1} />;
      case "transit": return <Bus size={14} className="text-text-primary" strokeWidth={1} />;
      default: return <MapPin size={14} className="text-text-primary" strokeWidth={1} />;
    }
  };

  return (
    <div className="flex h-screen bg-bg-base overflow-hidden">
      {/* Left Column: Table */}
      <div className="w-[450px] shrink-0 border-r border-border flex flex-col h-full z-10 bg-bg-base relative shadow-2xl overflow-y-auto">
        <div className="p-8">
          <header className="space-y-4 mb-8">
            <h1 className="text-4xl font-light tracking-tight text-text-primary">POI SPILLOVER</h1>
            <p className="text-text-secondary font-light text-xs tracking-wide leading-relaxed">
              Parking violations cluster near metro stations, malls, hospitals, and schools. Click a category to highlight affected hotspots on the map.
            </p>
          </header>

          {activeShare !== null && (
            <div className="bg-transparent border border-border p-6 mb-8">
              <div className="flex items-center justify-between mb-6">
                <div className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary">
                  {getCategoryTitle(activeCategoryStr)}
                </div>
                <CategoryIcon cat={activeCategoryStr} />
              </div>
              <div className="text-4xl font-light text-text-primary tracking-tight">
                {activeShare}%
              </div>
              <div className="text-[10px] text-text-secondary mt-2 tracking-wide">
                {getCategorySubtitle(activeCategoryStr)}
              </div>
            </div>
          )}

          <div className="border border-border overflow-hidden">
            <table className="w-full text-sm text-left">
              <thead className="text-[10px] text-text-secondary uppercase tracking-[0.2em] font-medium border-b border-border bg-text-primary/5">
                <tr>
                  <th className="px-4 py-4">Category</th>
                  <th className="px-4 py-4 text-right">Hotspots</th>
                  <th className="px-4 py-4 text-right">Violations</th>
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
                      <td className="px-4 py-4 text-right font-light text-text-secondary">{row.total_violations?.toLocaleString()}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          
          {selectedCategory ? (
            <div className="mt-8 p-4 border border-fuchsia-500/30 bg-fuchsia-900/10 text-xs text-text-secondary">
              Viewing <span className="text-fuchsia-400 font-bold uppercase">{selectedCategory}</span> hotspots. Map markers are highlighted in fuchsia.
            </div>
          ) : (
            <div className="mt-8 p-4 border border-border text-xs text-text-secondary">
              <p className="text-text-primary font-light mb-1">How to use this page</p>
              <p>Click a category to highlight hotspots on the map. Use the Live Map to plan patrol routes near high-density POI clusters.</p>
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
