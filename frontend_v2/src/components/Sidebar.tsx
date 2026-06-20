"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { LayoutDashboard, Map, TrendingUp, ShieldAlert, GitMerge, MapPin, Building2, Filter } from "lucide-react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { useEffect, useState, useCallback } from "react";
import { getStations, getStats } from "@/lib/api";

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [stations, setStations] = useState<string[]>([]);
  const [vehicles, setVehicles] = useState<string[]>([]);
  const [dateRange, setDateRange] = useState({ start: "?", end: "?" });

  // Filter state
  const station = searchParams.get("station") || "All stations";
  const vehicle = searchParams.get("vehicle") || "All types";
  const violation = searchParams.get("violation") || "All violations";
  const minRisk = searchParams.get("risk") || "0";

  useEffect(() => {
    getStations().then((res) => {
      setStations(res.map((s: any) => s.police_station).sort());
    });
    getStats().then((res) => {
      if (res?.by_vehicle_type) {
        setVehicles(Object.keys(res.by_vehicle_type).sort());
      }
      if (res?.date_range) {
        setDateRange(res.date_range);
      }
    });
  }, []);

  const updateFilter = useCallback((key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString());
    
    // Check if the value is a default reset value
    const isDefault = 
      (key === "station" && value === "All stations") ||
      (key === "vehicle" && value === "All types") ||
      (key === "violation" && value === "All violations") ||
      (key === "risk" && value === "0");

    if (isDefault) {
      params.delete(key);
    } else {
      params.set(key, value);
    }

    router.push(`${pathname}?${params.toString()}`);
  }, [pathname, router, searchParams]);

  const links = [
    { href: "/", label: "Overview", icon: LayoutDashboard },
    { href: "/map", label: "Live Map", icon: Map },
    { href: "/forecast", label: "Forecasts", icon: TrendingUp },
    { href: "/deploy", label: "Patrol Deployment", icon: ShieldAlert },
    { href: "/poi", label: "POI Spillover", icon: MapPin },
    { href: "/temporal", label: "Temporal Dist.", icon: Filter },
    { href: "/stations", label: "Stations", icon: Building2 },
    { href: "/junctions", label: "Junctions", icon: GitMerge },
  ];

  return (
    <aside className="w-72 border-r border-border bg-bg-base flex flex-col h-screen fixed left-0 top-0 overflow-y-auto">
      <div className="p-8 border-b border-border sticky top-0 bg-bg-base z-10">
        <h1 className="text-text-primary font-black tracking-tighter text-2xl uppercase">TRINETRA</h1>
        <p className="text-text-secondary text-[10px] mt-1 tracking-widest uppercase font-light">Traffic Intelligence</p>
      </div>

      <nav className="p-4 space-y-1">
        {links.map((link) => {
          const Icon = link.icon;
          const isActive = pathname === link.href;

          return (
            <Link
              key={link.href}
              href={`${link.href}?${searchParams.toString()}`}
              className={cn(
                "flex items-center gap-4 px-4 py-3 text-xs font-medium tracking-[0.1em] uppercase transition-all duration-300",
                isActive 
                  ? "text-text-primary border-l-2 border-text-primary bg-bg-elevated/20" 
                  : "text-text-secondary hover:text-text-primary border-l-2 border-transparent"
              )}
            >
              <Icon size={14} className={isActive ? "text-text-primary" : "text-text-secondary"} strokeWidth={1.5} />
              {link.label}
            </Link>
          );
        })}
      </nav>

      {/* Control Panel Filters */}
      <div className="px-8 py-8 mt-4 space-y-8 flex-1">
        <div className="text-[10px] font-medium tracking-[0.2em] text-text-secondary uppercase mb-6">
          Control Panel
        </div>

        <div className="space-y-3">
          <label className="text-[9px] font-medium text-text-secondary uppercase tracking-[0.15em] block">Police Station</label>
          <select 
            value={station}
            onChange={(e) => updateFilter("station", e.target.value)}
            className="w-full bg-transparent border border-border rounded-none px-4 py-3 text-xs text-text-primary focus:outline-none focus:border-text-secondary appearance-none"
          >
            <option className="bg-bg-base">All stations</option>
            {stations.map((s) => <option className="bg-bg-base" key={s} value={s}>{s}</option>)}
          </select>
        </div>

        <div className="space-y-3">
          <label className="text-[9px] font-medium text-text-secondary uppercase tracking-[0.15em] block">Vehicle Type</label>
          <select 
            value={vehicle}
            onChange={(e) => updateFilter("vehicle", e.target.value)}
            className="w-full bg-transparent border border-border rounded-none px-4 py-3 text-xs text-text-primary focus:outline-none focus:border-text-secondary appearance-none"
          >
            <option className="bg-bg-base">All types</option>
            {vehicles.map((v) => <option className="bg-bg-base" key={v} value={v}>{v}</option>)}
          </select>
        </div>

        <div className="space-y-3">
          <label className="text-[9px] font-medium text-text-secondary uppercase tracking-[0.15em] block">Violation Type</label>
          <select 
            value={violation}
            onChange={(e) => updateFilter("violation", e.target.value)}
            className="w-full bg-transparent border border-border rounded-none px-4 py-3 text-xs text-text-primary focus:outline-none focus:border-text-secondary appearance-none"
          >
            <option className="bg-bg-base">All violations</option>
            <option className="bg-bg-base">NO PARKING</option>
            <option className="bg-bg-base">WRONG PARKING</option>
            <option className="bg-bg-base">PARKING IN A MAIN ROAD</option>
            <option className="bg-bg-base">PARKING NEAR ROAD CROSSING</option>
            <option className="bg-bg-base">PARKING ON FOOTPATH</option>
          </select>
        </div>

        <div className="space-y-3">
          <div className="flex justify-between items-baseline">
            <label className="text-[9px] font-medium text-text-secondary uppercase tracking-[0.15em] block">Min Risk Score</label>
            <span className="text-xs font-light text-text-primary">{minRisk}</span>
          </div>
          <input 
            type="range" 
            min="0" 
            max="65" 
            step="5"
            value={minRisk}
            onChange={(e) => updateFilter("risk", e.target.value)}
            className="w-full accent-text-primary"
          />
        </div>

        <div className="space-y-3 pb-8">
          <div className="flex justify-between items-baseline">
            <label className="text-[9px] font-medium text-text-secondary uppercase tracking-[0.15em] block">Patrol Units</label>
            <span className="text-xs font-light text-text-primary">{searchParams.get("units") || "20"}</span>
          </div>
          <input 
            type="range" 
            min="0" 
            max="100" 
            step="1"
            value={searchParams.get("units") || "20"}
            onChange={(e) => updateFilter("units", e.target.value)}
            className="w-full accent-text-primary"
          />
        </div>

        <div className="mt-auto pt-8 border-t border-border">
          <div className="px-4 py-3 border border-border text-[9px] text-text-secondary text-center font-light uppercase tracking-[0.2em]">
            {dateRange.start} — {dateRange.end}
          </div>
        </div>
      </div>
    </aside>
  );
}
