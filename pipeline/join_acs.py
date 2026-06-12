"""Load ACS S0101 population, separating the Texas state row from counties."""
import pandas as pd

from . import config


def load_acs(path=config.ACS_CSV):
    """Return (county_pop_df, texas_totals_dict).

    Read with the machine-name header (row 1); row 2 holds human labels and is
    dropped. County names are reduced to Census short form ("Anderson").
    """
    raw = pd.read_csv(path, header=0, dtype=str)
    raw = raw.iloc[1:].copy()  # drop the label row

    total = config.ACS_TOTAL_POP
    seniors = config.ACS_SENIORS

    tx = raw[raw["NAME"] == "Texas"].iloc[0]
    texas = {
        "total_pop": int(tx[total]),
        "seniors": int(tx[seniors]),
    }

    counties = raw[raw["NAME"] != "Texas"].copy()
    counties["County"] = counties["NAME"].str.replace(" County, Texas", "", regex=False)
    counties["total_pop"] = counties[total].astype(int)
    counties["seniors"] = counties[seniors].astype(int)
    county_pop = counties[["County", "total_pop", "seniors"]].reset_index(drop=True)
    return county_pop, texas
