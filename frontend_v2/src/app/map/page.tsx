import { getHotspots, getPatrol } from "@/lib/api";
import MapWrapper from "@/components/MapWrapper";

export default async function MapPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const params = await searchParams;
  const filters: { limit: number; [key: string]: any } = { limit: 1200 };
  if (params.station) filters.police_station = params.station;
  if (params.vehicle) filters.vehicle_type = params.vehicle;
  if (params.violation) filters.violation_type = params.violation;
  if (params.risk) filters.min_risk = params.risk;

  const hotspots = await getHotspots(filters);
  const units = parseInt(params.units || "0", 10);
  const patrolData = units > 0 ? await getPatrol(units) : null;
  const assignments = patrolData?.assignments?.map((a: any) => a.hotspot_id) || [];

  return (
    <div className="w-full h-screen bg-bg-base p-8">
      <div className="w-full h-full">
        <MapWrapper hotspots={hotspots} assignments={assignments} />
      </div>
    </div>
  );
}
