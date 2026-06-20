"use client";

import dynamic from "next/dynamic";

const LiveMap = dynamic(() => import("./LiveMap"), { ssr: false });

export default function MapWrapper({ hotspots, assignments = [] }: { hotspots: any[], assignments?: string[] }) {
  return <LiveMap hotspots={hotspots} assignments={assignments} />;
}
