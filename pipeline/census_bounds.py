"""Census reporting bounds and tier reporting rates (rule R3).

`Current client census` is reported at parent, branch, and ADS level; where a
parent AND its branches both report, inclusion is ambiguous. Statewide census is
reported as a range:
  upper = sum across all locations
  lower = per license, max(parent value, sum of branch/ADS values) when both
          sides > 0, else their sum.
"""
import pandas as pd

PARENT_TYPES = {"Parent Agency"}
BRANCH_TYPES = {"Branch Agency", "Alternate Delivery Site"}


def _census(df):
    return pd.to_numeric(df["Current client census"], errors="coerce").fillna(0.0)


def statewide_range(df):
    """Return (lower, upper) statewide census across all locations."""
    c = _census(df)
    upper = float(c.sum())

    work = df[["License No", "Agency Type"]].copy()
    work["census"] = c
    is_parent = work["Agency Type"].isin(PARENT_TYPES)
    work["parent_val"] = work["census"].where(is_parent, 0.0)
    work["branch_val"] = work["census"].where(~is_parent, 0.0)

    grp = work.groupby("License No")[["parent_val", "branch_val"]].sum()
    both = (grp["parent_val"] > 0) & (grp["branch_val"] > 0)
    contrib = (grp[["parent_val", "branch_val"]].max(axis=1)
               .where(both, grp["parent_val"] + grp["branch_val"]))
    lower = float(contrib.sum())
    return lower, upper


def tier_census(df):
    """Per-tier total census (upper-style sum) and location-level reporting rate."""
    c = _census(df)
    work = df[["Tier"]].copy()
    work["census"] = c
    work["reported"] = pd.to_numeric(df["Current client census"], errors="coerce").notna()

    rows = {}
    for tier, sub in work.groupby("Tier"):
        rows[tier] = {
            "census": float(sub["census"].sum()),
            "reporting_rate": float(sub["reported"].mean()),
            "locations": int(len(sub)),
        }
    return rows


def avg_clients_per_certified_agency(df, cbsa_for_county):
    """Avg certified census per certified agency, by CBSA.

    Numerator: total certified-tier census across locations in the CBSA.
    Denominator: distinct License No with a certified location in the CBSA (R2).
    """
    cert = df[df["Tier"] == "Medicare-certified HH"].copy()
    cert["census"] = _census(cert)
    cert["CBSA"] = cert["County"].map(cbsa_for_county)

    out = {}
    for cbsa, sub in cert.groupby("CBSA"):
        agencies = sub["License No"].nunique()
        if agencies == 0:
            continue
        out[cbsa] = float(sub["census"].sum()) / agencies
    return out
