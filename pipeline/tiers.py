"""Assign a service tier to each location from `Services Provided`."""
import pandas as pd

from . import config


def assign_tier(services):
    if pd.isna(services):
        return None
    text = str(services)
    for substring, label in config.TIER_RULES:
        if substring in text:
            return label
    return None


def add_tier(df):
    df = df.copy()
    df["Tier"] = df["Services Provided"].map(assign_tier)
    return df
