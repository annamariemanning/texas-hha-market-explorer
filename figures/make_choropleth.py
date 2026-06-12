"""Static choropleth for the memo: Texas counties shaded by Medicare-certified
home health agencies per 10,000 seniors (65+).

Standalone — reads outputs/county_master.csv (does NOT touch the pipeline or the
explorer). County geometry: U.S. Census 2023 cartographic boundary file
(cb_2023_us_county_500k), joined to the pipeline's normalized county names.

Run:  .venv/bin/python figures/make_choropleth.py
"""
from pathlib import Path

import geopandas as gpd
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.cm import ScalarMappable
from matplotlib.colors import TwoSlopeNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parent.parent
SHP = ROOT / "figures" / "_geo" / "cb_2023_us_county_500k.shp"
CM = ROOT / "outputs" / "county_master.csv"
OUT = ROOT / "figures" / "texas_certified_density_choropleth.png"

BENCH = 4.49  # statewide certified per 10K seniors (matches explorer stat card)
METRIC = "certified_per_10k_seniors"
I35 = {
    "Austin-Round Rock-San Marcos, TX": "Austin",
    "San Antonio-New Braunfels, TX": "San Antonio",
    "Killeen-Temple, TX": "Killeen–Temple",
    "Waco, TX": "Waco",
}


def main():
    cm = pd.read_csv(CM)
    tx = gpd.read_file(SHP)
    tx = tx.loc[tx["STATEFP"] == "48", ["NAME", "geometry"]].copy()

    # Join on the pipeline's normalized county name (NAME == County). Verified
    # earlier: all 254 match exactly (McLennan / McCulloch / Jim Wells included).
    g = tx.merge(cm, left_on="NAME", right_on="County", how="left",
                 validate="one_to_one")
    missing = g["County"].isna().sum()
    assert missing == 0, f"{missing} counties failed to join"
    g = g.to_crs(epsg=3083)  # Texas Centric Albers Equal Area

    # Spot-check three counties against county_master before exporting.
    print("Spot-check (map value vs county_master):")
    ref = cm.set_index("County")
    for name in ("McLennan", "Travis", "Loving"):
        row = g.loc[g["NAME"] == name].iloc[0]
        src = ref.loc[name]
        print(f"  {name:10s} cert/10k={row[METRIC]:6.2f} (csv {src[METRIC]:6.2f})"
              f"  agencies={int(row['agencies'])} certified={int(row['Medicare-certified HH'])}")

    gray = g["agencies"] == 0                # 71 counties: no licensed agency at all
    colored = g[~gray]
    graycty = g[gray]
    print(f"\nGray (no licensed agencies): {len(graycty)} counties; "
          f"colored: {len(colored)} counties; metric range "
          f"{colored[METRIC].min():.2f}-{colored[METRIC].max():.2f}")

    vmax = float(g[METRIC].max())
    norm = TwoSlopeNorm(vmin=0.0, vcenter=BENCH, vmax=vmax)  # 4.49 -> color midpoint
    cmap = plt.get_cmap("YlGnBu")

    fig, ax = plt.subplots(figsize=(11, 12), dpi=300)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    colored.plot(column=METRIC, cmap=cmap, norm=norm, ax=ax,
                 edgecolor="white", linewidth=0.3)
    graycty.plot(color="#cfd2d6", ax=ax, edgecolor="white", linewidth=0.3)
    g.boundary.plot(ax=ax, color="#9aa0a6", linewidth=0.15)

    # I-35 corridor metros: dissolve member counties, outline + label.
    i35 = g[g["CBSA"].isin(I35)].dissolve(by="CBSA")
    i35.boundary.plot(ax=ax, color="#e8730c", linewidth=1.8)
    for cbsa, row in i35.iterrows():
        pt = row.geometry.representative_point()
        ax.annotate(I35[cbsa], xy=(pt.x, pt.y), ha="center", va="center",
                    fontsize=9.5, fontweight="bold", color="#7a3d00",
                    path_effects=[pe.withStroke(linewidth=2.6, foreground="white")])

    ax.set_axis_off()
    ax.set_title("Texas home health market: Medicare-certified agency density by county",
                 fontsize=15, fontweight="bold", pad=12)
    ax.text(0.5, 1.005,
            "Counties shaded by certified agencies per 10,000 seniors (65+); "
            "I-35 corridor metros outlined in orange",
            transform=ax.transAxes, ha="center", va="bottom",
            fontsize=10, color="#444")

    # Colorbar with the benchmark marked as a threshold (red line + red tick).
    sm = ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.032, pad=0.02, shrink=0.62)
    cbar.set_label("Medicare-certified home health agencies\nper 10,000 seniors (65+)",
                   fontsize=10)
    cbar.set_ticks([0, BENCH, 10, 20])
    cbar.set_ticklabels(["0", "4.49", "10", "20"])
    cbar.ax.axhline(BENCH, color="#b00020", linewidth=1.4)
    for t in cbar.ax.get_yticklabels():
        if t.get_text() == "4.49":
            t.set_color("#b00020")
            t.set_fontweight("bold")

    legend = [
        Patch(facecolor="#cfd2d6", edgecolor="white", label="No licensed agencies (0)"),
        Line2D([0], [0], color="#e8730c", lw=1.8, label="I-35 corridor metro"),
        Line2D([0], [0], color="#b00020", lw=1.4, label="State benchmark: 4.49 per 10K seniors"),
    ]
    ax.legend(handles=legend, loc="lower left", frameon=True, fontsize=9,
              facecolor="white", edgecolor="#cccccc")

    fig.savefig(OUT, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"\nWrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
