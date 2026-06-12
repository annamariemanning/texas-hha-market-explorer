"""Shared paths and analytical constants for the Texas HHA pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "Data"
OUTPUTS = ROOT / "outputs"

# Input files. The spec names ./data/ACSST5Y2024_S0101-Data.csv; the actual
# export ships the ACS CSV under a subfolder with a dot in the name.
MARCH_XLSX = DATA / "Texas_HHA_-_2026-03-01_Export.xlsx"
JUNE_XLSX = DATA / "HHA.xlsx"
ACS_CSV = DATA / "ACSST5Y2024" / "ACSST5Y2024.S0101-Data.csv"
DELINEATION_XLSX = DATA / "list1_2023.xlsx"

HCSSA_SHEET = "HCSSA_Directory"

# ACS S0101 column codes
ACS_TOTAL_POP = "S0101_C01_001E"
ACS_SENIORS = "S0101_C01_030E"  # 65 years and over

# County name normalization: directory style -> Census style.
COUNTY_NORMALIZE = {
    "Mclennan": "McLennan",
    "Mcculloch": "McCulloch",
    "Jim Wells County": "Jim Wells",
}

# Service tiers: (substring, tier label), first match wins in this order.
TIER_RULES = [
    ("Licensed and Certified Home Health", "Medicare-certified HH"),
    ("Licensed Home Health", "Licensed-only HH"),
    ("Hospice", "Hospice"),
    ("Personal Assistance", "PAS only"),
]
TIER_ORDER = [label for _, label in TIER_RULES]

# I-35 corridor CBSAs for highlighting.
I35_CORRIDOR = [
    "Austin-Round Rock-San Marcos, TX",
    "San Antonio-New Braunfels, TX",
    "Killeen-Temple, TX",
    "Waco, TX",
]

RURAL_LABEL = "Rural Texas"
