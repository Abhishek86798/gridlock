import { getPoiStats } from "@/lib/api";

export const revalidate = 60;

export default async function PoiPage() {
  const data = await getPoiStats();
  const byCat = data?.by_category || [];

  return (
    <div className="p-12 max-w-7xl mx-auto space-y-12 bg-bg-base min-h-screen">
      <header className="space-y-4">
        <h1 className="text-5xl font-light tracking-tight text-text-primary">POI SPILLOVER</h1>
        <p className="text-text-secondary font-light text-sm tracking-wide">
          Analysis of parking violations around major Points of Interest (Metro, Malls, Tech Parks)
        </p>
      </header>

      <div className="border border-border overflow-hidden">
        <table className="w-full text-sm text-left">
          <thead className="text-[10px] text-text-secondary uppercase tracking-[0.2em] font-medium border-b border-border bg-text-primary/5">
            <tr>
              <th className="px-8 py-6">POI Category</th>
              <th className="px-8 py-6 text-right">Hotspots Tagged</th>
              <th className="px-8 py-6 text-right">Total Violations</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {byCat.map((row: any, i: number) => (
              <tr key={i} className="hover:bg-text-primary/5 transition-colors">
                <td className="px-8 py-6 font-light text-text-primary">{row.poi_category}</td>
                <td className="px-8 py-6 text-right font-light text-text-primary">{row.hotspot_count}</td>
                <td className="px-8 py-6 text-right font-light text-text-secondary">{row.total_violations}</td>
              </tr>
            ))}
            {byCat.length === 0 && (
              <tr>
                <td colSpan={3} className="px-8 py-12 text-center text-text-secondary font-light tracking-wide">No POI data available.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
