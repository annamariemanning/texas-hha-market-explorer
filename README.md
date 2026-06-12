# Texas Home Health Market Penetration

Analysis pipeline and interactive market explorer for home health agency
penetration in Texas. Built for a take-home assessment.

## Live explorer

**https://annamariemanning.github.io/texas-hha-market-explorer/**

A single self-contained HTML page (all data inlined, no server) showing distinct
agency counts, Medicare-certified density per 10K seniors, and reported patient
census by metro/CBSA and by county — with an I-35 corridor filter, a state
benchmark (4.49 certified per 10K seniors), and an embedded statewide choropleth.

## Data sources

- **Texas HHSC HCSSA Directory** — Home and Community Support Services Agency
  licensing directory. Snapshots: 2026-03-01 (base) and 2026-06-11 (dynamics update).
- **U.S. Census Bureau, ACS 2024 5-Year Estimates, Table S0101** (Age and Sex) —
  Texas and all 254 counties; total population (`S0101_C01_001E`) and 65+
  (`S0101_C01_030E`).
- **OMB July 2023 CBSA delineations**, Bulletin No. 23-01 (`list1_2023.xlsx`) —
  metropolitan and micropolitan statistical areas; non-CBSA counties roll up to
  "Rural Texas."

## Run

```bash
python3 -m venv .venv
.venv/bin/python -m pip install pandas openpyxl
.venv/bin/python -m pipeline.run_all
```

`run_all` reads the files in `Data/`, runs the full pipeline, prints the
checkpoint report, and writes results to `outputs/`. To regenerate the
self-contained explorer afterward:

```bash
.venv/bin/python -m pipeline.build_explorer   # writes texas_hha_market_explorer.html
```

## Verification

Every key figure the pipeline produces — distinct agency counts, by-tier
breakdowns, densities, census ranges, and the June snapshot deltas — is checked
against a pre-validated target value. `run_all` runs all 67 checkpoints and emits
a pass/fail report; the build fails loudly if any figure drifts. The full report
is written to `outputs/checkpoint_report.txt` (currently **67/67 PASS**).

## Repo map

| Path | Contents |
| --- | --- |
| `pipeline/` | Pipeline scripts: load/clean, service-tier assignment, ACS join, CBSA rollup, census bounds, metrics, June delta, orchestrator (`run_all.py`), explorer generator (`build_explorer.py`) |
| `Data/` | Source files: HCSSA directory exports, ACS S0101 CSVs, OMB CBSA delineations |
| `outputs/` | Generated CSVs (`county_master`, `cbsa_rollup`, `census_by_metro`) and `checkpoint_report.txt` |
| `figures/` | Static choropleth map (`make_choropleth.py` + PNG) embedded in the explorer |
| `texas_hha_market_explorer.html`, `index.html` | The self-contained interactive explorer (also published to GitHub Pages) |
| `CLAUDE_1.md` | Analysis design spec the pipeline implements |
