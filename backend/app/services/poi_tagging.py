"""
Step 5.3 — POI / Spillover Tagging.

Keyword-matches location text (and junction_name) to assign each violation
to one of four POI categories, then aggregates to hotspot level, populating
`poi_category` and `near_poi`.

Why text-only (no geofencing radius)?
  The dataset has no external POI database. The `location` column is the rich
  address string logged by enforcement officers — it is Bengaluru-specific and
  frequently names the facility directly. Keyword matching on that text is
  more reliable and self-contained than a radius query against an external
  dataset (which could cause PS1 disqualification if mis-classified as an
  "external dataset").

Category priority (highest → lowest):
  sensitive   — schools, colleges, hospitals (highest enforcement concern)
  metro       — metro stations (mobility choke-points)
  commercial  — malls, markets, bazaars, complexes
  transit     — bus stands, bus stops

A hotspot's `poi_category` is the **highest-priority category** found across
all its member violations. `near_poi` stores the most common location text
fragment that triggered the match (useful as a human-readable label in the UI).

Public API
----------
tag_violations(df)  → df with added `poi_category` / `poi_label` columns
tag_hotspots(violations, hotspots) → hotspots with `poi_category` / `near_poi`
"""
from __future__ import annotations

import re
from typing import Optional

import pandas as pd

# ── Keyword taxonomy ──────────────────────────────────────────────────────────
#
# Each category maps to a list of keywords to search for (case-insensitive,
# full-word boundary anchored so "market" doesn't fire on "supermarket road").
# Add synonyms here; the codebase does not need to change elsewhere.

_KEYWORDS: dict[str, list[str]] = {
    # Schools / colleges / hospitals — highest enforcement priority
    "sensitive": [
        "school", "college", "university", "hospital", "clinic",
        "medical", "nursing home", "health centre", "health center",
        "primary school", "high school", "matriculation",
    ],
    # Metro / rail stations — mobility choke-points
    "metro": [
        "metro", "namma metro", "metro station", "railway station",
        "rail station", "junction station",
    ],
    # Commercial / retail hubs
    "commercial": [
        "mall", "market", "complex", "bazaar", "bazar",
        "shopping", "plaza", "arcade", "commercial street",
        "city market", "retail",
    ],
    # Bus infrastructure
    "transit": [
        "bus stop", "bus stand", "bus station", "bus depot",
        "ksrtc", "bmtc depot",
    ],
}

# Priority order — first match wins when a hotspot has multiple categories.
_PRIORITY: list[str] = ["sensitive", "metro", "commercial", "transit"]

# Pre-compile one combined regex per category for speed.
_PATTERNS: dict[str, re.Pattern] = {
    cat: re.compile(
        r"\b(?:" + "|".join(re.escape(kw) for kw in kws) + r")\b",
        re.IGNORECASE,
    )
    for cat, kws in _KEYWORDS.items()
}


# ── Row-level tagging ─────────────────────────────────────────────────────────

def _text_for_row(row: pd.Series) -> str:
    """Concatenate all location-bearing text columns for a violation row."""
    parts: list[str] = []
    for col in ("location", "junction_name", "police_station"):
        val = row.get(col)
        if pd.notna(val) and isinstance(val, str) and val.strip():
            parts.append(val.strip())
    return " | ".join(parts)


def _classify_text(text: str) -> tuple[Optional[str], Optional[str]]:
    """
    Match text against all keyword categories in priority order.

    Returns
    -------
    category : str or None
        Highest-priority category matched, or None.
    label : str or None
        The matched keyword phrase (first match), used as near_poi label.
    """
    for cat in _PRIORITY:
        m = _PATTERNS[cat].search(text)
        if m:
            return cat, m.group(0).lower()
    return None, None


def tag_violations(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add ``poi_category`` and ``poi_label`` columns to a violations DataFrame.

    Parameters
    ----------
    df:
        Violations DataFrame with at least ``location`` and ``junction_name``
        columns (output of build_features / clean_violations).

    Returns
    -------
    pd.DataFrame
        Same rows + two new string columns.  Unmatched rows have None/NaN.
    """
    texts = df.apply(_text_for_row, axis=1)

    categories: list[Optional[str]] = []
    labels: list[Optional[str]] = []
    for text in texts:
        cat, lbl = _classify_text(text)
        categories.append(cat)
        labels.append(lbl)

    out = df.copy()
    out["poi_category"] = categories
    out["poi_label"]    = labels
    return out


# ── Hotspot-level aggregation ─────────────────────────────────────────────────

def tag_hotspots(
    violations: pd.DataFrame,
    hotspots: pd.DataFrame,
) -> pd.DataFrame:
    """
    Populate ``poi_category`` and ``near_poi`` on the hotspots DataFrame
    by aggregating violation-level POI tags within each hotspot's H3 cell.

    Parameters
    ----------
    violations:
        Violations DataFrame **that already has** a ``hex_id`` column and
        optionally ``poi_category`` / ``poi_label`` columns.  If the tag
        columns are absent they will be derived here.
    hotspots:
        Hotspots DataFrame (output of compute_hotspots), with ``hex_id``
        and ``near_poi`` columns.

    Returns
    -------
    pd.DataFrame
        Hotspots with ``poi_category`` and ``near_poi`` updated.
    """
    # Ensure violations have POI columns.
    if "poi_category" not in violations.columns:
        violations = tag_violations(violations)

    # Reduce violations to tagged rows only, keep minimal columns.
    tagged = violations.dropna(subset=["poi_category"]).copy()

    if "hex_id" not in tagged.columns:
        # hex_id not yet assigned — we can still match on hotspot centroid
        # text, but that's less accurate. Fall back gracefully.
        hotspots = hotspots.copy()
        hotspots["poi_category"] = None
        # near_poi already exists as None placeholder — leave it.
        return hotspots

    # Per hex_id: highest-priority category + most frequent label.
    def _agg_hex(grp: pd.DataFrame) -> pd.Series:
        # priority: sensitive > metro > commercial > transit
        found_cats = set(grp["poi_category"].dropna().unique())
        best_cat = next((c for c in _PRIORITY if c in found_cats), None)

        # Most common label within that best category.
        if best_cat:
            lbls = grp.loc[
                grp["poi_category"] == best_cat, "poi_label"
            ].dropna()
            best_lbl = str(lbls.mode().iloc[0]) if len(lbls) else None
        else:
            best_lbl = None

        return pd.Series({"poi_category": best_cat, "near_poi": best_lbl})

    hex_tags = (
        tagged.groupby("hex_id", sort=False)
        .apply(_agg_hex)
        .reset_index()
    )  # columns: hex_id, poi_category, near_poi

    # Merge onto hotspots, overwriting the None placeholder.
    out = hotspots.copy()
    # Drop existing poi/near columns if already present from a stale run.
    for col in ("poi_category", "near_poi"):
        if col in out.columns and col != "near_poi":
            out = out.drop(columns=[col])

    out = out.merge(
        hex_tags[["hex_id", "poi_category", "near_poi"]],
        on="hex_id",
        how="left",
        suffixes=("_old", ""),
    )

    # If merge created *_old duplicates (near_poi already existed), clean up.
    for col in list(out.columns):
        if col.endswith("_old"):
            out = out.drop(columns=[col])

    return out


# ── Summary helper (for precompute logs) ─────────────────────────────────────

def poi_summary(hotspots: pd.DataFrame) -> str:
    """Return a human-readable POI coverage summary string."""
    total = len(hotspots)
    tagged = hotspots["poi_category"].notna().sum()
    lines = [
        f"   POI-tagged hotspots : {tagged:,} / {total:,} "
        f"({tagged / total * 100:.1f}%)",
    ]
    if "poi_category" in hotspots.columns:
        for cat in _PRIORITY:
            n = (hotspots["poi_category"] == cat).sum()
            if n:
                lines.append(f"     {cat:<12} {n:>5}")
    return "\n".join(lines)
