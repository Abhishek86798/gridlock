import sys
sys.path.insert(0, ".")
from backend.app.core.config import settings
import pandas as pd

temporal = pd.read_parquet(settings.temporal_parquet)
hotspots = pd.read_parquet(settings.hotspots_parquet)

hs_total = temporal.groupby("hotspot_id")["count"].sum().rename("total_count")
coverage = temporal.groupby("hotspot_id").size().rename("cell_count")
combined = pd.concat([hs_total, coverage], axis=1)
combined["sparse"] = combined["cell_count"] < 5

sparse_df = combined[combined["sparse"]]
dense_df = combined[~combined["sparse"]]

total_traffic = combined["total_count"].sum()
sparse_traffic = sparse_df["total_count"].sum()

print("Sparse hotspots (<5 cells):")
print("  count:             ", len(sparse_df))
print("  total violations:  ", sparse_df["total_count"].sum())
print("  median violations: ", sparse_df["total_count"].median())
print("  max violations:    ", sparse_df["total_count"].max())
print("  pct of traffic:    ", round(sparse_traffic / total_traffic * 100, 1))
print()
print("Dense hotspots (>=5 cells):")
print("  count:             ", len(dense_df))
print("  median violations: ", dense_df["total_count"].median())
print()

hs_station = hotspots[["hotspot_id", "police_station"]].set_index("hotspot_id")
combined2 = combined.join(hs_station)
station_sparse = combined2.groupby("police_station").apply(
    lambda g: round(g["sparse"].sum() / len(g), 2)
).rename("sparse_frac")
print("Stations with >40% sparse hotspots:")
result = station_sparse[station_sparse > 0.4].sort_values(ascending=False)
print(result.to_string() if len(result) else "  None")
print()
print("All station sparse fractions (sorted):")
print(station_sparse.sort_values(ascending=False).to_string())
