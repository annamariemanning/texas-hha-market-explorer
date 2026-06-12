"""Load and clean an HHSC HCSSA directory snapshot.

A row is a licensed LOCATION (Parent / Branch / Alternate Delivery Site).
Distinct agencies == unique License No (rule R1).
"""
import pandas as pd

from . import config


def load_directory(path):
    """Read the HCSSA_Directory sheet; the real header is the second row."""
    df = pd.read_excel(path, sheet_name=config.HCSSA_SHEET, header=1)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def normalize_county(name):
    if pd.isna(name):
        return name
    name = str(name).strip()
    return config.COUNTY_NORMALIZE.get(name, name)


def clean(df):
    """Drop EXPIRED rows and normalize county names.

    ENFORCEMENT ACTION PEND and RENEWAL IN PROCESS are kept (footnoted).
    Returns (cleaned_df, footnotes_dict).
    """
    status = df["License Status"].astype(str).str.strip()
    expired_mask = status == "EXPIRED"
    footnotes = {
        "expired_dropped": int(expired_mask.sum()),
        "enforcement_action_pend": int((status == "ENFORCEMENT ACTION PEND").sum()),
        "renewal_in_process": int((status == "RENEWAL IN PROCESS").sum()),
    }
    out = df.loc[~expired_mask].copy()
    out["County"] = out["County"].map(normalize_county)
    return out, footnotes


def assert_counties_match(df, acs_counties):
    """All directory counties must match ACS county names exactly."""
    dir_counties = set(df["County"].dropna().unique())
    unmatched = sorted(dir_counties - set(acs_counties))
    assert not unmatched, f"Unmatched directory counties: {unmatched}"
