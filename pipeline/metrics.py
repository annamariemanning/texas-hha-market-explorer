"""Shared dedup-aware counting (rules R1/R2).

Never sum lower-level distinct counts to get a higher-level figure — every
distinct-agency count is a fresh nunique(License No) at that geography/tier.
"""
import pandas as pd

from . import config


def distinct_agencies(df):
    return int(df["License No"].nunique())


def locations_by_tier(df):
    """Location count per tier (each location has exactly one tier)."""
    return df["Tier"].value_counts().to_dict()


def distinct_by_tier(df):
    """Distinct License No with >=1 location in each tier (may overlap)."""
    return {t: int(sub["License No"].nunique()) for t, sub in df.groupby("Tier")}


def license_primary_tier(df):
    """Map License No -> single highest-priority tier across its locations."""
    order = {label: i for i, label in enumerate(config.TIER_ORDER)}
    tmp = df[["License No", "Tier"]].dropna(subset=["Tier"]).copy()
    tmp["rank"] = tmp["Tier"].map(order)
    idx = tmp.groupby("License No")["rank"].idxmin()
    return tmp.loc[idx].set_index("License No")["Tier"]


def metro_rollup(df, cbsa_for_county):
    """Per-CBSA distinct agencies (all tiers) and certified-tier distinct (R2)."""
    work = df.copy()
    work["CBSA"] = work["County"].map(cbsa_for_county)
    rows = []
    cert = work[work["Tier"] == "Medicare-certified HH"]
    cert_by_cbsa = cert.groupby("CBSA")["License No"].nunique()
    for cbsa, sub in work.groupby("CBSA"):
        rows.append({
            "CBSA": cbsa,
            "agencies": int(sub["License No"].nunique()),
            "certified": int(cert_by_cbsa.get(cbsa, 0)),
        })
    return pd.DataFrame(rows).sort_values("agencies", ascending=False).reset_index(drop=True)
