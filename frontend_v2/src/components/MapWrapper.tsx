"use client";

import dynamic from "next/dynamic";

const LiveMap = dynamic(() => import("./LiveMap"), { ssr: false });

export default function MapWrapper({ hotspots, assignments = [], highlightPoi }: { hotspots: any[], assignments?: any[], highlightPoi?: string | null }) {
  return <LiveMap hotspots={hotspots} assignments={assignments} highlightPoi={highlightPoi} />;
}
