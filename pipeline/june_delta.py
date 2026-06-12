"""Market-dynamics delta between the March and June snapshots.

Identical cleaning is applied to both. Compare sets of License No:
  new     = in June not March
  dropped = in March not June

new/dropped-by-tier attribute each license to its single primary tier
(partition; sums to the total). net-by-tier compares the distinct-by-tier
counts (>=1 location in tier; rule R2) between snapshots.
"""
import pandas as pd

from . import load_clean, tiers, metrics


def load_clean_snapshot(path):
    raw = load_clean.load_directory(path)
    cleaned, _ = load_clean.clean(raw)
    cleaned = tiers.add_tier(cleaned)
    return cleaned


def compute_delta(march_df, june_df):
    march_lic = set(march_df["License No"].unique())
    june_lic = set(june_df["License No"].unique())

    new = june_lic - march_lic
    dropped = march_lic - june_lic

    march_primary = metrics.license_primary_tier(march_df)
    june_primary = metrics.license_primary_tier(june_df)

    new_by_tier = june_primary.loc[list(new)].value_counts().to_dict()
    dropped_by_tier = march_primary.loc[list(dropped)].value_counts().to_dict()

    march_dbt = metrics.distinct_by_tier(march_df)
    june_dbt = metrics.distinct_by_tier(june_df)
    tiers_all = set(march_dbt) | set(june_dbt)
    net_by_tier = {t: int(june_dbt.get(t, 0) - march_dbt.get(t, 0)) for t in tiers_all}

    return {
        "june_locations": int(len(june_df)),
        "june_distinct": int(len(june_lic)),
        "n_new": len(new),
        "n_dropped": len(dropped),
        "net": len(new) - len(dropped),
        "new_by_tier": new_by_tier,
        "dropped_by_tier": dropped_by_tier,
        "net_by_tier": net_by_tier,
    }
