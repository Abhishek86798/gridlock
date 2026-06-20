import { getStations } from "@/lib/api";

export const revalidate = 60;

export default async function StationsPage() {
  const data = await getStations();
  const stations = data || [];

  return (
    <div className="p-12 max-w-7xl mx-auto space-y-12 bg-bg-base min-h-screen">
      <header className="space-y-4">
        <h1 className="text-5xl font-light tracking-tight text-text-primary">POLICE STATIONS</h1>
        <p className="text-text-secondary font-light text-sm tracking-wide">
          Enforcement metrics across all 53 precinct zones
        </p>
      </header>

      <div className="border border-border overflow-hidden">
        <table className="w-full text-sm text-left">
          <thead className="text-[10px] text-text-secondary uppercase tracking-[0.2em] font-medium border-b border-border bg-text-primary/5">
            <tr>
              <th className="px-8 py-6">Station Name</th>
              <th className="px-8 py-6 text-right">Hotspots</th>
              <th className="px-8 py-6 text-right">Violations</th>
              <th className="px-8 py-6 text-right">Avg Risk</th>
              <th className="px-8 py-6 text-right">Blind Spot %</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {stations.map((row: any, i: number) => (
              <tr key={i} className="hover:bg-text-primary/5 transition-colors">
                <td className="px-8 py-6 font-light text-text-primary">{row.police_station}</td>
                <td className="px-8 py-6 text-right font-light text-text-secondary">{row.hotspot_count}</td>
                <td className="px-8 py-6 text-right font-light text-text-primary">{row.total_violations}</td>
                <td className="px-8 py-6 text-right font-light text-text-secondary">{row.avg_risk_score?.toFixed(1)}</td>
                <td className={`px-8 py-6 text-right font-light ${row.blind_spot_pct > 70 ? 'text-critical' : 'text-text-muted'}`}>
                  {row.blind_spot_pct?.toFixed(1)}%
                </td>
              </tr>
            ))}
            {stations.length === 0 && (
              <tr>
                <td colSpan={5} className="px-8 py-12 text-center text-text-secondary font-light tracking-wide">No station data available.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
