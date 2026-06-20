import { getPoiStats, getHotspots } from "@/lib/api";
import PoiClient from "./PoiClient";

export const revalidate = 60;

export default async function PoiPage() {
  const data = await getPoiStats();
  const byCat = data?.by_category || [];
  
  // Fetch all hotspots (backend max limit is 1200) to ensure all POI-tagged ones are passed to the map
  const hotspots = await getHotspots({ limit: 1200 });

  return <PoiClient stats={byCat} hotspots={hotspots} />;
}
