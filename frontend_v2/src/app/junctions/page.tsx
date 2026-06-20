import { getJunctions } from "@/lib/api";

export const revalidate = 60;

export default async function JunctionsPage() {
  const data = await getJunctions({ min_violations: 50 });
  const junctions = data || [];

  return (
    <div className="p-12 max-w-7xl mx-auto space-y-12 bg-bg-base min-h-screen">
      <header className="space-y-4">
        <h1 className="text-5xl font-light tracking-tight text-text-primary">MAJOR JUNCTIONS</h1>
        <p className="text-text-secondary font-light text-sm tracking-wide">
          Identified intersections with 50+ violations
        </p>
      </header>

      <div className="border border-border overflow-hidden">
        <table className="w-full text-sm text-left">
          <thead className="text-[10px] text-text-secondary uppercase tracking-[0.2em] font-medium border-b border-border bg-text-primary/5">
            <tr>
              <th className="px-8 py-6">Junction Name</th>
              <th className="px-8 py-6 text-right">Violations</th>
              <th className="px-8 py-6 text-right">Avg Risk Score</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {junctions.map((row: any, i: number) => (
              <tr key={i} className="hover:bg-text-primary/5 transition-colors">
                <td className="px-8 py-6 font-light text-text-primary">{row.junction_name}</td>
                <td className="px-8 py-6 text-right font-light text-text-primary">{row.total_violations}</td>
                <td className="px-8 py-6 text-right font-light text-text-secondary">{row.avg_risk_score?.toFixed(1)}</td>
              </tr>
            ))}
            {junctions.length === 0 && (
              <tr>
                <td colSpan={3} className="px-8 py-12 text-center text-text-secondary font-light tracking-wide">No junction data available.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
