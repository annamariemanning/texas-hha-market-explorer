"""Run the full Texas HHA pipeline, write outputs, and verify every checkpoint.

Usage:  python -m pipeline.run_all
"""
import io

import pandas as pd

from . import config, load_clean, tiers, join_acs, rollup_cbsa, census_bounds, metrics, june_delta


# ---------------------------------------------------------------- checkpoints
class Checks:
    def __init__(self):
        self.rows = []  # (label, expected, actual, passed)

    def exact(self, label, expected, actual):
        self.rows.append((label, expected, actual, expected == actual))

    def approx(self, label, expected, actual, tol):
        ok = actual is not None and abs(actual - expected) <= tol
        self.rows.append((label, expected, round(actual, 2) if actual is not None else None, ok))

    def render(self):
        out = io.StringIO()
        npass = sum(1 for *_, p in self.rows if p)
        out.write(f"CHECKPOINT REPORT — {npass}/{len(self.rows)} PASS\n")
        out.write("=" * 72 + "\n")
        for label, exp, act, ok in self.rows:
            tag = "PASS" if ok else "FAIL"
            out.write(f"[{tag}] {label}\n")
            if not ok:
                out.write(f"        expected={exp!r}  actual={act!r}\n")
        return out.getvalue(), npass == len(self.rows)


def find_cbsa(delineation, keyword):
    """Resolve a checkpoint's short metro name to its full CBSA title."""
    titles = delineation.loc[
        delineation["CBSA"].str.contains(keyword, case=False, na=False), "CBSA"
    ].unique()
    return titles[0] if len(titles) else None


# ---------------------------------------------------------------- build
def build():
    march_raw = load_clean.load_directory(config.MARCH_XLSX)
    march, footnotes = load_clean.clean(march_raw)
    march = tiers.add_tier(march)

    county_pop, texas = join_acs.load_acs()
    load_clean.assert_counties_match(march, county_pop["County"])

    delineation = rollup_cbsa.load_delineation()
    cbsa_for_county = dict(zip(delineation["County"], delineation["CBSA"]))

    def cbsa_of(c):
        return cbsa_for_county.get(c, config.RURAL_LABEL)

    # --- county master ---
    grp = march.groupby("County")
    county_master = pd.DataFrame({
        "agencies": grp["License No"].nunique(),
        "locations": grp.size(),
    })
    for tier in config.TIER_ORDER:
        sub = march[march["Tier"] == tier].groupby("County")["License No"].nunique()
        county_master[tier] = sub
    county_master = county_master.reindex(county_pop["County"]).fillna(0)
    for col in county_master.columns:
        county_master[col] = county_master[col].astype(int)
    county_master = county_master.merge(county_pop, left_index=True, right_on="County")
    county_master["CBSA"] = county_master["County"].map(cbsa_of)
    county_master["certified_per_10k_seniors"] = (
        county_master["Medicare-certified HH"] / county_master["seniors"] * 10000
    ).round(3)
    county_master["agencies_per_100k_pop"] = (
        county_master["agencies"] / county_master["total_pop"] * 100000
    ).round(3)

    # Current client census per geography (Q2): sum across reporting locations
    # ("upper" measure) + location-level reporting rate.
    march_census = census_bounds._census(march)
    cen = march[["County"]].copy()
    cen["census"] = march_census
    cen["reported"] = march["Current client census"].notna().values
    county_cen = cen.groupby("County").agg(census=("census", "sum"), rate=("reported", "mean"))
    county_master["census"] = county_master["County"].map(county_cen["census"]).fillna(0).round().astype(int)
    county_master["census_reporting_pct"] = (
        county_master["County"].map(county_cen["rate"]).fillna(0) * 100
    ).round(1)
    county_master = county_master.sort_values("County").reset_index(drop=True)

    # --- CBSA rollup (R2 recompute) ---
    cbsa_roll = metrics.metro_rollup(march, cbsa_of)
    seniors_by_cbsa = county_master.groupby("CBSA")["seniors"].sum()
    pop_by_cbsa = county_master.groupby("CBSA")["total_pop"].sum()
    cbsa_roll["seniors"] = cbsa_roll["CBSA"].map(seniors_by_cbsa)
    cbsa_roll["total_pop"] = cbsa_roll["CBSA"].map(pop_by_cbsa)
    cbsa_roll["certified_per_10k_seniors"] = (
        cbsa_roll["certified"] / cbsa_roll["seniors"] * 10000
    ).round(2)
    cbsa_roll["agencies_per_100k_pop"] = (
        cbsa_roll["agencies"] / cbsa_roll["total_pop"] * 100000
    ).round(2)
    cen_cbsa = cen.assign(CBSA=cen["County"].map(cbsa_of)).groupby("CBSA").agg(
        census=("census", "sum"), rate=("reported", "mean"))
    cbsa_roll["census"] = cbsa_roll["CBSA"].map(cen_cbsa["census"]).fillna(0).round().astype(int)
    cbsa_roll["census_reporting_pct"] = (
        cbsa_roll["CBSA"].map(cen_cbsa["rate"]).fillna(0) * 100).round(1)

    # --- census ---
    lower, upper = census_bounds.statewide_range(march)
    tier_cen = census_bounds.tier_census(march)
    avg_cert = census_bounds.avg_clients_per_certified_agency(march, cbsa_of)
    census_by_metro = pd.DataFrame(
        [{"CBSA": k, "avg_clients_per_certified_agency": round(v, 1)} for k, v in avg_cert.items()]
    )
    census_by_metro["total_census"] = census_by_metro["CBSA"].map(cen_cbsa["census"]).round().astype(int)
    census_by_metro["reporting_pct"] = (census_by_metro["CBSA"].map(cen_cbsa["rate"]) * 100).round(1)
    census_by_metro = census_by_metro.sort_values("CBSA").reset_index(drop=True)

    # --- whitespace ---
    cbsa_type = dict(zip(delineation["County"], delineation["CBSA_type"]))
    zero_counties = county_master[county_master["locations"] == 0]
    zero_in_metro = zero_counties[zero_counties["County"].map(cbsa_type)
                                  == "Metropolitan Statistical Area"]

    # --- june ---
    june = june_delta.load_clean_snapshot(config.JUNE_XLSX)
    delta = june_delta.compute_delta(march, june)

    return dict(
        march=march, march_raw=march_raw, footnotes=footnotes, texas=texas,
        county_master=county_master, cbsa_roll=cbsa_roll, delineation=delineation,
        lower=lower, upper=upper, tier_cen=tier_cen, census_by_metro=census_by_metro,
        zero_counties=zero_counties, zero_in_metro=zero_in_metro, delta=delta,
        avg_cert=avg_cert,
    )


def verify(b):
    c = Checks()
    march, raw = b["march"], b["march_raw"]
    texas = b["texas"]
    delin = b["delineation"]

    # March post-clean
    c.exact("March: locations (post-clean)", 8496, len(march))
    c.exact("March: distinct agencies", 7482, metrics.distinct_agencies(march))
    dbt = metrics.distinct_by_tier(march)
    c.exact("March: certified distinct", 1822, dbt.get("Medicare-certified HH"))
    c.exact("March: licensed-only distinct", 1661, dbt.get("Licensed-only HH"))
    c.exact("March: hospice distinct", 1167, dbt.get("Hospice"))
    c.exact("March: PAS-only distinct", 2940, dbt.get("PAS only"))

    at = march["Agency Type"].value_counts()
    c.exact("March: Parent rows", 7482, int(at.get("Parent Agency", 0)))
    c.exact("March: Branch rows", 623, int(at.get("Branch Agency", 0)))
    c.exact("March: ADS rows", 391, int(at.get("Alternate Delivery Site", 0)))
    c.exact("March raw: rows", 8505, len(raw))
    c.exact("March raw: distinct licenses (incl expired)", 7491, int(raw["License No"].nunique()))

    # ACS / state
    c.exact("ACS: Texas total pop", 30188424, texas["total_pop"])
    c.exact("ACS: Texas 65+", 4056252, texas["seniors"])
    c.approx("ACS: 65+ share %", 13.4, texas["seniors"] / texas["total_pop"] * 100, 0.05)
    statewide_cert_per10k = dbt["Medicare-certified HH"] / texas["seniors"] * 10000
    c.approx("State: certified per 10K seniors", 4.49, statewide_cert_per10k, 0.01)

    # Metro rollup
    roll = b["cbsa_roll"].set_index("CBSA")
    metros = {
        "DFW": ("Dallas", 2352, 654, 6.76),
        "Houston": ("Houston", 2471, 464, 5.05),
        "San Antonio": ("San Antonio", 545, 91, 2.46),
        "Austin": ("Austin", 337, 65, 2.24),
        "Killeen-Temple": ("Killeen", 64, 15, 2.48),
        "Waco": ("Waco", 44, 10, 2.05),
    }
    for name, (kw, ag, cert, per10k) in metros.items():
        title = find_cbsa(delin, kw)
        row = roll.loc[title] if title in roll.index else None
        c.exact(f"Metro {name}: agencies", ag, int(row["agencies"]) if row is not None else None)
        c.exact(f"Metro {name}: certified", cert, int(row["certified"]) if row is not None else None)
        c.approx(f"Metro {name}: certified per 10K seniors", per10k,
                 float(row["certified_per_10k_seniors"]) if row is not None else None, 0.02)
    for name, kw, per10k in [("McAllen", "McAllen", 8.42), ("Laredo", "Laredo", 14.78)]:
        title = find_cbsa(delin, kw)
        row = roll.loc[title] if title in roll.index else None
        c.approx(f"Metro {name}: certified per 10K seniors", per10k,
                 float(row["certified_per_10k_seniors"]) if row is not None else None, 0.02)

    # Census
    c.exact("Census: statewide lower", 634524, round(b["lower"]))
    c.exact("Census: statewide upper", 703647, round(b["upper"]))
    tc = b["tier_cen"]
    c.exact("Census: certified-tier total", 311003, round(tc["Medicare-certified HH"]["census"]))
    c.approx("Census: certified reporting %", 97.4, tc["Medicare-certified HH"]["reporting_rate"] * 100, 0.1)
    c.approx("Census: PAS reporting %", 49.3, tc["PAS only"]["reporting_rate"] * 100, 0.1)
    c.approx("Census: licensed-only reporting %", 60.2, tc["Licensed-only HH"]["reporting_rate"] * 100, 0.1)
    c.approx("Census: hospice reporting %", 80.2, tc["Hospice"]["reporting_rate"] * 100, 0.1)

    avg = b["avg_cert"]
    for name, kw, exp in [("Houston", "Houston", 107), ("DFW", "Dallas", 127), ("Waco", "Waco", 254),
                          ("San Antonio", "San Antonio", 266), ("Austin", "Austin", 364),
                          ("Killeen-Temple", "Killeen", 401)]:
        title = find_cbsa(delin, kw)
        c.approx(f"Census: avg clients/certified agency {name}", exp,
                 avg.get(title), 1.0)

    # Whitespace
    zc = b["zero_counties"]
    c.exact("Whitespace: zero-location counties", 71, len(zc))
    c.exact("Whitespace: zero-county population", 466928, int(zc["total_pop"].sum()))
    c.exact("Whitespace: zero-county seniors", 94814, int(zc["seniors"].sum()))
    c.exact("Whitespace: zero-agency counties in metros", 15, len(b["zero_in_metro"]))
    if len(b["zero_in_metro"]):
        largest = b["zero_in_metro"].sort_values("total_pop", ascending=False).iloc[0]
        c.exact("Whitespace: largest zero-agency metro county", "Caldwell", largest["County"])
        c.exact("Whitespace: Caldwell population", 48669, int(largest["total_pop"]))

    # June delta
    d = b["delta"]
    c.exact("June: locations", 8675, d["june_locations"])
    c.exact("June: distinct agencies", 7604, d["june_distinct"])
    c.exact("June: new licenses", 355, d["n_new"])
    c.exact("June: dropped licenses", 233, d["n_dropped"])
    c.exact("June: net change", 122, d["net"])
    nbt = d["new_by_tier"]
    c.exact("June new by tier: PAS", 247, nbt.get("PAS only"))
    c.exact("June new by tier: licensed-only", 69, nbt.get("Licensed-only HH"))
    c.exact("June new by tier: hospice", 32, nbt.get("Hospice"))
    c.exact("June new by tier: certified", 7, nbt.get("Medicare-certified HH"))
    net = d["net_by_tier"]
    c.exact("June net distinct by tier: PAS", 143, net.get("PAS only"))
    c.exact("June net distinct by tier: licensed-only", -10, net.get("Licensed-only HH"))
    c.exact("June net distinct by tier: certified", -13, net.get("Medicare-certified HH"))
    c.exact("June net distinct by tier: hospice", -2, net.get("Hospice"))

    return c


def write_outputs(b, report_text):
    config.OUTPUTS.mkdir(exist_ok=True)
    b["county_master"].to_csv(config.OUTPUTS / "county_master.csv", index=False)
    b["cbsa_roll"].to_csv(config.OUTPUTS / "cbsa_rollup.csv", index=False)
    b["census_by_metro"].to_csv(config.OUTPUTS / "census_by_metro.csv", index=False)
    (config.OUTPUTS / "checkpoint_report.txt").write_text(report_text)


def main():
    b = build()
    checks = verify(b)
    report_text, all_pass = checks.render()
    write_outputs(b, report_text)
    print(report_text)
    fn = b["footnotes"]
    print(f"Footnotes: kept {fn['enforcement_action_pend']} enforcement-action-pend, "
          f"{fn['renewal_in_process']} renewal-in-process; dropped {fn['expired_dropped']} expired.")
    print("ALL CHECKPOINTS PASS" if all_pass else "SOME CHECKPOINTS FAILED — see report.")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
