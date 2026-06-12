"""Map Texas counties to CBSAs (OMB July 2023 delineations).

Counties outside any CBSA are labeled "Rural Texas".
"""
import pandas as pd

from . import config


def load_delineation(path=config.DELINEATION_XLSX):
    """Return a county -> CBSA dataframe for Texas (FIPS state 48)."""
    d = pd.read_excel(path, header=2)
    d = d[d["FIPS State Code"] == 48].copy()
    d["County"] = d["County/County Equivalent"].str.replace(" County", "", regex=False).str.strip()
    d = d.rename(columns={
        "CBSA Title": "CBSA",
        "Metropolitan/Micropolitan Statistical Area": "CBSA_type",
    })
    return d[["County", "CBSA", "CBSA_type"]].reset_index(drop=True)


def attach_cbsa(county_df, delineation):
    """Left-join CBSA onto a county-level dataframe; fill non-CBSA as Rural."""
    out = county_df.merge(delineation, on="County", how="left")
    out["CBSA"] = out["CBSA"].fillna(config.RURAL_LABEL)
    out["CBSA_type"] = out["CBSA_type"].fillna(config.RURAL_LABEL)
    return out
