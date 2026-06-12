# Texas Home Health Market Penetration — Analysis Pipeline

Implementation of the analysis design in [`CLAUDE_1.md`](CLAUDE_1.md). The design is
final; this repo implements it as a reproducible pipeline and verifies every
checkpoint. All 67 checkpoints currently **PASS**.

## Live explorer

**https://annamariemanning.github.io/texas-hha-market-explorer/** (GitHub Pages)

The explorer is a single self-contained HTML file — all data is inlined as JSON,
no server or external dependencies — so it also opens by double-clicking
`texas_hha_market_explorer.html` locally.

Restart the local preview server (then open http://localhost:8765/):

```bash
.venv/bin/python -m http.server 8765 --bind 127.0.0.1
```

Rebuild outputs + explorer and republish to Pages after any change:

```bash
.venv/bin/python -m pipeline.run_all && .venv/bin/python -m pipeline.build_explorer && git commit -am "Rebuild outputs and explorer" && git push
```

## Run

```bash
python3 -m venv .venv
.venv/bin/python -m pip install pandas openpyxl
.venv/bin/python -m pipeline.run_all
```

`run_all` prints the checkpoint report with PASS/FAIL and writes `outputs/`.

Regenerate the interactive explorer (self-contained, opens with no server):

```bash
.venv/bin/python -m pipeline.build_explorer   # writes texas_hha_market_explorer.html
```

## Pipeline (`pipeline/`)

| Module | Responsibility |
| --- | --- |
| `config.py` | Paths, county normalization map, tier rules, I-35 corridor |
| `load_clean.py` | Read HCSSA sheet (header=1), drop EXPIRED, normalize counties, assert county match |
| `tiers.py` | Service-tier assignment (first match wins) |
| `join_acs.py` | ACS S0101 population; separate Texas state row from counties |
| `rollup_cbsa.py` | County → CBSA (OMB 2023); non-CBSA → "Rural Texas" |
| `census_bounds.py` | Statewide census range (R3), tier reporting rates, avg clients/certified agency |
| `metrics.py` | Dedup-aware counts (R1/R2): distinct agencies, by-tier, metro rollup |
| `june_delta.py` | New/dropped license sets between snapshots |
| `run_all.py` | Orchestrator + checkpoint verification + output writer |
| `build_explorer.py` | Emits the self-contained `texas_hha_market_explorer.html` |

## Outputs (`outputs/`)

- `county_master.csv` — per county: distinct agencies (total + by tier; "agencies
  with a location in county"), locations, population, seniors, CBSA, densities,
  `census` (total Current client census) + `census_reporting_pct`.
- `cbsa_rollup.csv` — per CBSA, R2-deduped: agencies, certified, seniors,
  certified per 10K seniors, agencies per 100K pop, `census` + `census_reporting_pct`.
- `census_by_metro.csv` — avg clients per certified agency, total census, and
  reporting rate, by CBSA.
- `checkpoint_report.txt` — full PASS/FAIL report.

## Key counting rules (do not sum across levels)

- **R1** — a row is a licensed *location*; distinct agencies = unique `License No`.
- **R2** — within any geography, count distinct `License No` with ≥1 location
  there. County rows do **not** sum to metro totals; metros do **not** sum to the
  statewide distinct total. Recompute `nunique` at each level.
- **R3** — census reported as a range: upper = sum across all locations; lower =
  per license, `max(parent, sum(branch/ADS))` when both > 0, else their sum.

## Data sources & citations

- **Texas HHSC HCSSA Directory** — Home and Community Support Services Agency
  licensing directory. Snapshots: 2026-03-01 (active as of 2026-02-26; BASE) and
  2026-06-11 (dynamics delta only).
- **U.S. Census Bureau, ACS 2024 5-Year Estimates, Table S0101** (Age and Sex),
  Texas and 254 counties. Columns `S0101_C01_001E` (total population),
  `S0101_C01_030E` (65 years and over).
- **OMB July 2023 delineations**, Bulletin No. 23-01 (`list1_2023.xlsx`):
  26 Texas metropolitan and 41 micropolitan CBSAs; 121 counties are non-CBSA
  ("Rural Texas").

## Caveats (carry into any write-up)

- `Current client census` is self-reported, point-in-time, all payers; ~31% of
  locations blank. Reporting rates vary sharply by tier (PAS 49.3% → certified 97.4%).
- HQ location ≠ service coverage; agencies serve across county lines.
- 373 agencies have enforcement actions pending — kept in counts, footnoted.
  193 renewal-in-process also kept; 9 expired licenses dropped.
- Metro definitions use the current in-force 2023 OMB standard.

## Notes / deviations

- The ACS CSV ships as `Data/ACSST5Y2024/ACSST5Y2024.S0101-Data.csv` (dot, in a
  subfolder), not the `./data/ACSST5Y2024_S0101-Data.csv` path named in the spec.
  `config.py` points at the actual location.
- The interactive explorer (`texas_hha_market_explorer.html`) was not present in
  the input set; it is generated fresh by `pipeline/build_explorer.py`. It embeds
  CBSA-level rows with R2 dedup and county rows labeled "agencies with a location
  in county"; data is inlined as JSON so the file opens directly (no server).

## Explorer features

- Toggle **Metros / CBSA** vs **Counties** views.
- Density toggle: **per 10K seniors** (headline) vs **per 100K population**.
- Sortable columns, name filter, and an **I-35 corridor only** filter (Austin,
  San Antonio, Killeen-Temple, Waco — highlighted with an orange bar).
- Summary cards (distinct agencies, certified density, 65+ share, census range,
  whitespace) and a **June 2026 dynamics** panel (new / dropped / net by tier).
