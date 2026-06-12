# Texas Home Health Market Penetration — Analysis Pipeline

## Context
Take-home assessment (Part 1) for Adaptive Innovations: analyze home health agency
penetration across Texas geographies using the Texas HHSC HCSSA directory plus public
population data. The analytical design is FINAL — your job is to implement it as a
clean, reproducible pipeline and verify outputs against the checkpoints below.
Do not revisit the design decisions; flag (don't fix) any checkpoint mismatch.

## Input files (expected in ./data/)
1. `Texas_HHA_-_2026-03-01_Export.xlsx` — HHSC HCSSA directory, active licenses as of
   2026-02-26. BASE snapshot for all analysis.
2. `HHA.xlsx` — same directory, as of 2026-06-11. Used ONLY for the market-dynamics
   delta (new/dropped licenses).
3. `ACSST5Y2024_S0101-Data.csv` — ACS 2024 5-Year, Table S0101, Texas + 254 counties.
   Population columns: S0101_C01_001E (total), S0101_C01_030E (65+).
4. `list1_2023.xlsx` — OMB July 2023 CBSA delineations (Bulletin 23-01).

## Parsing rules
- Both HHSC files: sheet `HCSSA_Directory`, real header is the SECOND row (header=1).
- ACS file: data headers are in the first row (machine names) with labels in row 2;
  read with the machine-name header. State row ("Texas") is included — separate it.
- Delineation file: header row 3 (header=2); filter `FIPS State Code` == 48.

## Locked analytical decisions

### Cleaning
- Drop rows with `License Status` == "EXPIRED" (9 rows in March file). Keep
  ENFORCEMENT ACTION PEND and RENEWAL IN PROCESS (footnote them; do not drop).
- County name normalization (directory → Census style):
  `Mclennan→McLennan`, `Mcculloch→McCulloch`, `Jim Wells County→Jim Wells`.
  After normalization, ALL directory counties must match ACS county names exactly
  (assert zero unmatched).

### Service tiers (from `Services Provided`, first match wins, in this order)
1. contains "Licensed and Certified Home Health"  → `Medicare-certified HH`
2. contains "Licensed Home Health"                → `Licensed-only HH`
3. contains "Hospice"                             → `Hospice`
4. contains "Personal Assistance"                 → `PAS only`

### Deduplication rules (critical)
- R1 — Unit of count: a row is a licensed LOCATION. Parents, branches, and
  alternate delivery sites share one `License No`. "Distinct agencies" = unique
  License No.
- R2 — Geographic counting: within any geography, count distinct License No that
  have ≥1 location in that geography. Consequence: a multi-county agency counts
  once per county it's in, but only once per metro; county rows therefore do NOT
  sum to metro totals, and metro totals do NOT sum to the statewide distinct total.
  Never sum lower-level distinct counts to get a higher-level figure — recompute
  nunique at each level.
- R3 — Census bounds: `Current client census` is reported at parent, branch, and
  ADS level; where a parent AND its branches both report, inclusion is ambiguous.
  Report statewide census as a range:
  upper = sum across all locations; lower = per license, max(parent value,
  sum of branch/ADS values) when both sides > 0, else their sum.

### Geography
- Atomic unit: county (native to both datasets; exhaustive; stable boundaries).
- Rollup: county → CBSA via list1_2023 (26 TX metros, 41 micropolitans);
  counties outside any CBSA = "Rural Texas" (121 counties).
- Density denominators: report BOTH per 100K total population and per 10K seniors
  (65+); per-senior is the headline metric.
- I-35 corridor set (for highlighting): Austin-Round Rock-San Marcos,
  San Antonio-New Braunfels, Killeen-Temple, Waco.

### June update (dynamics)
- Apply identical cleaning to both snapshots. Compare sets of License No:
  new = in June not March; dropped = in March not June. Report by tier and county.

## Verification checkpoints (must match exactly)
March snapshot, post-clean:
- 8,496 locations; 7,482 distinct agencies.
- Distinct agencies by tier: certified 1,822 · licensed-only 1,661 ·
  hospice 1,167 · PAS-only 2,940.
- Agency Type rows: Parent 7,482 · Branch ~623 · ADS ~391 (pre-clean raw file
  has 8,505 rows; 7,491 distinct licenses incl. expired).

ACS / state:
- Texas pop 30,188,424; 65+ 4,056,252 (13.4%).
- Statewide certified per 10K seniors (deduped): 4.49.

Metro rollup (March, R2 dedup): 
- DFW 2,352 agencies / 654 certified; Houston 2,471 / 464; San Antonio 545 / 91;
  Austin 337 / 65; Killeen-Temple 64 / 15; Waco 44 / 10.
- Certified per 10K seniors: Waco 2.05 · Austin 2.24 · San Antonio 2.46 ·
  Killeen-Temple 2.48 · Houston 5.05 · DFW 6.76 · McAllen 8.42 · Laredo 14.78.

Census (March):
- Statewide reported range: 634,524 (lower) – 703,647 (upper).
- Certified-tier census 311,003 at 97.4% location-level reporting.
  (Reporting rates: PAS 49.3%, licensed-only 60.2%, hospice 80.2%.)
- Avg clients per certified agency: Houston ≈107 · DFW ≈127 · Waco ≈254 ·
  San Antonio ≈266 · Austin ≈364 · Killeen-Temple ≈401.

Whitespace:
- 71 counties with zero licensed locations; pop 466,928; seniors 94,814.
- 15 zero-agency counties are inside metros; largest = Caldwell (48,669, Austin MSA).

June delta:
- June post-clean: 8,675 locations / 7,604 distinct agencies.
- 355 new licenses, 233 dropped, net +122.
- New by tier: PAS 247 · licensed-only 69 · hospice 32 · certified 7.
- Distinct-agency net change by tier: PAS +143 · licensed-only −10 ·
  certified −13 · hospice −2.

## Deliverables
1. `pipeline/` — small scripts (or one module): load_clean.py, tiers.py,
   join_acs.py, rollup_cbsa.py, census_bounds.py, june_delta.py + a runner
   (Makefile or run_all.py) that prints every checkpoint with PASS/FAIL.
2. `outputs/` — county_master.csv, cbsa_rollup.csv, census_by_metro.csv,
   checkpoint_report.txt.
3. The interactive explorer (already built: texas_hha_market_explorer.html) may be
   regenerated from the pipeline data; if regenerating, embed CBSA-level rows with
   R2 dedup and county rows labeled "agencies with a location in county."
4. README.md — sources & citations:
   - Texas HHSC HCSSA Directory (snapshots 2026-03-01, 2026-06-11)
   - U.S. Census Bureau, ACS 2024 5-Year Estimates, Table S0101
   - OMB July 2023 delineations (Bulletin No. 23-01)

## Known caveats to carry into any write-up
- Census field: self-reported, point-in-time, all payers; 31% of locations blank.
- HQ location ≠ service coverage (agencies serve across county lines).
- 373 agencies have enforcement actions pending (kept in counts; footnoted).
- Metro definitions: 2023 delineations are the current, in-force OMB standard.
