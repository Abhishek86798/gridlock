import Link from "next/link";
import { getStats, getPriority } from "@/lib/api";
import { ShieldAlert, MapPin, Building2, EyeOff } from "lucide-react";

export const revalidate = 60; // revalidate every minute

export default async function OverviewPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const params = await searchParams;
  const filters: Record<string, any> = { limit: 50 };
  if (params.station) filters.police_station = params.station;
  if (params.vehicle) filters.vehicle_type = params.vehicle;
  if (params.violation) filters.violation_type = params.violation;
  if (params.risk) filters.min_risk = params.risk;

  const [stats, priorityRows] = await Promise.all([
    getStats(),
    getPriority(filters),
  ]);

  const byStation = stats?.by_police_station || {};
  const topStation = Object.keys(byStation).length > 0 
    ? Object.keys(byStation).reduce((a, b) => byStation[a] > byStation[b] ? a : b) 
    : "—";

  const totalViolations = stats?.total_violations || 0;
  const totalHotspots = stats?.total_hotspots || 0;
  
  // Dynamic blind spot avg from backend (fallback to 0 if missing)
  const blindAvg = stats?.blind_spot_pct || 0;

  return (
    <div className="p-12 max-w-7xl mx-auto space-y-12 bg-bg-base min-h-screen">
      <header className="space-y-4">
        <h1 className="text-5xl font-light tracking-tight text-text-primary">OVERVIEW</h1>
        <p className="text-text-secondary font-light text-sm tracking-wide max-w-xl">
          Real-time monitoring of parking violations and traffic risk metrics.
        </p>
      </header>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <KpiCard title="Total Violations" value={totalViolations.toLocaleString()} icon={ShieldAlert} />
        <KpiCard title="Hotspot Zones" value={totalHotspots.toLocaleString()} icon={MapPin} />
        <KpiCard title="Busiest Station" value={topStation} icon={Building2} />
        <KpiCard title="Afternoon Blind Spot" value={`${blindAvg}%`} icon={EyeOff} />
      </div>

      {/* Priority Queue */}
      <div className="border border-border">
        <div className="p-5 border-b border-border">
          <h2 className="text-xs font-light uppercase tracking-[0.2em] text-text-secondary">
            Enforcement Priority Queue
          </h2>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-text-secondary uppercase border-b border-border">
              <tr>
                <th className="px-6 py-4 font-light tracking-wider">#</th>
                <th className="px-6 py-4 font-light tracking-wider">Zone</th>
                <th className="px-6 py-4 font-light tracking-wider text-right">Risk Score (0–100)</th>
                <th className="px-6 py-4 font-light tracking-wider">Peak Block</th>
                <th className="px-6 py-4 font-light tracking-wider">Station</th>
                <th className="px-6 py-4 font-light tracking-wider">Tier</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {priorityRows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-text-muted">
                    No priority data available.
                  </td>
                </tr>
              ) : (
                priorityRows.map((row: any, i: number) => (
                  <tr key={row.hotspot_id} className="hover:bg-bg-elevated/20 transition-colors">
                    <td className="px-6 py-4 text-text-muted">{i + 1}</td>
                    <td className="px-6 py-4 font-light text-text-primary">{row.hotspot_id}</td>
                    <td className="px-6 py-4 text-right font-mono text-text-secondary">{row.risk_score?.toFixed(1)}</td>
                    <td className="px-6 py-4 text-text-secondary">{row.logging_window}</td>
                    <td className="px-6 py-4 text-text-secondary">{row.police_station}</td>
                    <td className="px-6 py-4">
                      <TierBadge tier={row.priority_tier} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* CTA — bridge to Patrol Deployment */}
      <div className="border border-border p-6 flex items-center justify-between">
        <div>
          <p className="text-sm text-text-primary font-light">Ready to act on these hotspots?</p>
          <p className="text-xs text-text-secondary mt-1">Use Patrol Deployment to generate an optimised unit roster for next week.</p>
        </div>
        <Link href="/deploy" className="text-xs uppercase tracking-widest px-6 py-3 border border-border hover:bg-bg-elevated transition-colors">
          Go to Patrol Deployment →
        </Link>
      </div>
    </div>
  );
}

function KpiCard({ title, value, icon: Icon }: any) {
  return (
    <div className="bg-bg-elevated border border-border p-8 flex flex-col justify-between shadow-[0_8px_30px_rgba(255,255,255,0.02)] hover:-translate-y-1 hover:shadow-[0_8px_30px_rgba(255,255,255,0.05)] transition-all duration-300">
      <div className="flex items-center justify-between mb-8">
        <h3 className="text-[10px] font-light uppercase tracking-[0.2em] text-text-secondary">{title}</h3>
        <Icon size={16} className="text-text-primary" strokeWidth={1} />
      </div>
      <div className="text-4xl font-light text-text-primary tracking-tight">
        {value}
      </div>
    </div>
  );
}

function TierBadge({ tier }: { tier: string }) {
  const styles: Record<string, string> = {
    Critical: "text-red-400 border-red-500/50 bg-red-900/20",
    Elevated: "text-amber-400 border-amber-500/50 bg-amber-900/20",
    Standard: "text-text-muted border border-border",
  };
  
  return (
    <span className={`px-3 py-1.5 text-[9px] font-light uppercase tracking-[0.2em] rounded-none ${styles[tier] || styles.Standard}`}>
      {tier}
    </span>
  );
}
