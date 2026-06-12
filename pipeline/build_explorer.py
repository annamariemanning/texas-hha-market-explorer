"""Generate a self-contained interactive explorer HTML from pipeline data.

Embeds the computed tables as JSON so the file opens directly in a browser with
no server. CBSA rows use R2 dedup; county rows are labeled "agencies with a
location in county". Run:  python -m pipeline.build_explorer
"""
import base64
import json

from . import config, metrics, census_bounds
from .run_all import build, find_cbsa


TIERS = config.TIER_ORDER


def _cbsa_tier_table(march, cbsa_of):
    """Per-CBSA distinct agencies by tier (R2) + census + avg certified census."""
    work = march.copy()
    work["CBSA"] = work["County"].map(cbsa_of)
    work["census_num"] = census_bounds._census(work)
    rows = {}
    for cbsa, sub in work.groupby("CBSA"):
        d = {"agencies": int(sub["License No"].nunique())}
        for t in TIERS:
            d[t] = int(sub.loc[sub["Tier"] == t, "License No"].nunique())
        cert = sub[sub["Tier"] == "Medicare-certified HH"]
        n_cert = cert["License No"].nunique()
        d["cert_census"] = float(cert["census_num"].sum())
        d["avg_clients_per_certified"] = (float(cert["census_num"].sum()) / n_cert) if n_cert else 0.0
        rows[cbsa] = d
    return rows


def assemble(b):
    march = b["march"]
    delin = b["delineation"]
    cbsa_for_county = dict(zip(delin["County"], delin["CBSA"]))
    cbsa_type = dict(zip(delin["County"], delin["CBSA_type"]))

    def cbsa_of(c):
        return cbsa_for_county.get(c, config.RURAL_LABEL)

    tier_tbl = _cbsa_tier_table(march, cbsa_of)
    roll = b["cbsa_roll"].set_index("CBSA")

    # Total Current client census per geography (Q2): sum across all reporting
    # locations ("upper" measure), with the location-level reporting rate.
    census_num = census_bounds._census(march)
    reported = march["Current client census"].notna()
    cen = march[["County"]].copy()
    cen["CBSA"] = march["County"].map(cbsa_of)
    cen["census"] = census_num
    cen["reported"] = reported.values
    county_census = cen.groupby("County").agg(census=("census", "sum"),
                                              rate=("reported", "mean"))
    cbsa_census = cen.groupby("CBSA").agg(census=("census", "sum"),
                                          rate=("reported", "mean"))

    # I-35 corridor: resolve short names to full titles
    i35 = set()
    for kw in ["Austin", "San Antonio", "Killeen", "Waco"]:
        t = find_cbsa(delin, kw)
        if t:
            i35.add(t)

    def type_label(cbsa):
        if cbsa == config.RURAL_LABEL:
            return "Rural"
        # any county in this cbsa carries the type
        rows = delin.loc[delin["CBSA"] == cbsa, "CBSA_type"]
        v = rows.iloc[0] if len(rows) else ""
        return "Metro" if v == "Metropolitan Statistical Area" else "Micro"

    cbsa_rows = []
    for cbsa in roll.index:
        r = roll.loc[cbsa]
        t = tier_tbl.get(cbsa, {})
        cbsa_rows.append({
            "cbsa": cbsa,
            "type": type_label(cbsa),
            "i35": cbsa in i35,
            "agencies": int(r["agencies"]),
            "certified": int(r["certified"]),
            "licensed_only": t.get("Licensed-only HH", 0),
            "hospice": t.get("Hospice", 0),
            "pas": t.get("PAS only", 0),
            "seniors": int(r["seniors"]),
            "total_pop": int(r["total_pop"]),
            "cert_per_10k_sr": round(float(r["certified_per_10k_seniors"]), 2),
            "agencies_per_100k": round(float(r["agencies_per_100k_pop"]), 2),
            "census": int(round(cbsa_census.loc[cbsa, "census"])) if cbsa in cbsa_census.index else 0,
            "census_rate": round(float(cbsa_census.loc[cbsa, "rate"]) * 100, 0) if cbsa in cbsa_census.index else 0,
            "cert_census": int(round(t.get("cert_census", 0.0))),
            "avg_clients_certified": round(t.get("avg_clients_per_certified", 0.0), 1),
        })

    cm = b["county_master"]
    county_rows = []
    for _, r in cm.iterrows():
        county_rows.append({
            "county": r["County"],
            "cbsa": r["CBSA"],
            "type": type_label(r["CBSA"]),
            "agencies": int(r["agencies"]),
            "certified": int(r["Medicare-certified HH"]),
            "licensed_only": int(r["Licensed-only HH"]),
            "hospice": int(r["Hospice"]),
            "pas": int(r["PAS only"]),
            "locations": int(r["locations"]),
            "seniors": int(r["seniors"]),
            "total_pop": int(r["total_pop"]),
            "cert_per_10k_sr": round(float(r["certified_per_10k_seniors"]), 2),
            "agencies_per_100k": round(float(r["agencies_per_100k_pop"]), 2),
            "census": int(round(county_census.loc[r["County"], "census"])) if r["County"] in county_census.index else 0,
            "census_rate": round(float(county_census.loc[r["County"], "rate"]) * 100, 0) if r["County"] in county_census.index else 0,
        })

    dbt = metrics.distinct_by_tier(march)
    tc = b["tier_cen"]
    tx = b["texas"]
    d = b["delta"]
    zc = b["zero_counties"]

    summary = {
        "locations": int(len(march)),
        "agencies": metrics.distinct_agencies(march),
        "tier_distinct": {t: dbt.get(t, 0) for t in TIERS},
        "tier_reporting": {t: round(tc[t]["reporting_rate"] * 100, 1) for t in TIERS},
        "tier_census": {t: int(round(tc[t]["census"])) for t in TIERS},
        "texas_pop": tx["total_pop"],
        "texas_seniors": tx["seniors"],
        "senior_share": round(tx["seniors"] / tx["total_pop"] * 100, 1),
        "state_cert_per_10k": round(dbt["Medicare-certified HH"] / tx["seniors"] * 10000, 2),
        "census_lower": int(round(b["lower"])),
        "census_upper": int(round(b["upper"])),
        "whitespace_counties": int(len(zc)),
        "whitespace_pop": int(zc["total_pop"].sum()),
        "whitespace_seniors": int(zc["seniors"].sum()),
        "whitespace_in_metro": int(len(b["zero_in_metro"])),
        "june": d,
    }
    return {"summary": summary, "cbsa": cbsa_rows, "county": county_rows, "tiers": TIERS}


def map_section():
    """Build the embedded statewide-map section, or '' if the PNG is absent.

    The map is base64-inlined so the explorer stays self-contained (opens by
    double-click, no external assets). Generate the PNG with
    figures/make_choropleth.py; build_explorer only embeds the committed file.
    """
    png = config.ROOT / "figures" / "texas_certified_density_choropleth.png"
    if not png.exists():
        print(f"  (note: {png.name} not found — map section omitted)")
        return ""
    uri = "data:image/png;base64," + base64.b64encode(png.read_bytes()).decode("ascii")
    return (
        '  <div class="figsec">\n'
        "    <h3>Statewide map — certified density by county</h3>\n"
        '    <div class="figcard"><img alt="Texas counties shaded by Medicare-certified '
        'home health agencies per 10,000 seniors (65+); gray = no licensed agencies; '
        'I-35 corridor metros outlined in orange" src="' + uri + '"></div>\n'
        '    <div class="note">Medicare-certified home health agencies per 10,000 '
        "seniors (65+), by county. Gray = no licensed agencies. Sequential scale "
        "centered on the 4.49 statewide benchmark (red threshold); I-35 corridor metros "
        "(San Antonio, Austin, Killeen–Temple, Waco) outlined in orange. County geometry: "
        "U.S. Census 2023 cartographic boundaries.</div>\n"
        "  </div>\n"
    )


def render_html(data):
    payload = json.dumps(data, separators=(",", ":"))
    html = HTML_TEMPLATE.replace("__DATA__", payload)
    return html.replace("__MAPSECTION__", map_section())


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Texas Home Health Market Explorer</title>
<style>
  :root{
    --bg:#0f1419; --panel:#1a212b; --panel2:#222c38; --line:#2c3a48;
    --ink:#e6edf3; --muted:#8aa0b2; --accent:#4ea1ff; --i35:#ffb454;
    --cert:#4ea1ff; --pos:#3fb950; --neg:#f85149;
  }
  *{box-sizing:border-box}
  body{margin:0;font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    background:var(--bg);color:var(--ink)}
  header{padding:20px 24px;border-bottom:1px solid var(--line);background:var(--panel)}
  h1{margin:0 0 4px;font-size:20px}
  .sub{color:var(--muted);font-size:13px}
  .wrap{padding:18px 24px;max-width:1440px;margin:0 auto}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:18px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
  .card .k{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.04em}
  .card .v{font-size:22px;font-weight:600;margin-top:4px}
  .card .v small{font-size:12px;color:var(--muted);font-weight:400}
  .card .sub2{font-size:12px;color:var(--ink);opacity:.85;margin-top:5px}
  .card .ctx{font-size:11px;color:var(--muted);margin-top:4px;line-height:1.35}
  .controls{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:12px}
  .seg{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden}
  .seg button{background:var(--panel);color:var(--muted);border:0;padding:7px 14px;cursor:pointer;font-size:13px}
  .seg button.on{background:var(--accent);color:#04121f;font-weight:600}
  input[type=search]{background:var(--panel);border:1px solid var(--line);color:var(--ink);
    padding:7px 10px;border-radius:8px;min-width:200px;font-size:13px}
  label.chk{display:inline-flex;gap:6px;align-items:center;color:var(--muted);cursor:pointer;font-size:13px}
  table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}
  th,td{padding:7px 8px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
  th.tight,td.tight{padding-left:4px;padding-right:4px}
  th{position:sticky;top:0;z-index:2;background:var(--panel2);cursor:pointer;user-select:none;font-size:12px;color:var(--muted)}
  th.on{color:var(--accent)}
  th:first-child,td:first-child{text-align:left;position:sticky;left:0}
  td:first-child{z-index:1;background:var(--panel)}
  th:first-child{z-index:3}
  td.name{max-width:200px;overflow:hidden;text-overflow:ellipsis}
  tbody tr:hover{background:#202b37}
  tbody tr:hover td:first-child{background:#202b37}
  tr.i35 td:first-child{border-left:3px solid var(--i35);font-weight:600}
  .pill{display:inline-block;padding:1px 7px;border-radius:20px;font-size:11px;border:1px solid var(--line);color:var(--muted)}
  .pill.Metro{color:var(--accent);border-color:#2c4a6b}
  .pill.Micro{color:#b08cff;border-color:#3d3163}
  .pill.Rural{color:#7d8a97}
  .tablewrap{max-height:62vh;overflow:auto;border-radius:10px}
  .dim{color:var(--muted)}
  .below{color:var(--i35);font-weight:600}
  .i35key{color:var(--muted);font-size:13px}
  .i35bar{color:var(--i35);font-weight:700}
  .key{margin:2px 2px 12px}
  .note{color:var(--muted);font-size:12px;margin:10px 2px}
  .figsec{margin:22px 0 6px}
  .figsec h3{margin:0 0 8px;font-size:15px}
  .figcard{background:#f7f8fa;border:1px solid var(--line);border-radius:10px;padding:12px;text-align:center}
  .figcard img{max-width:760px;max-height:75vh;width:auto;height:auto;border-radius:6px}
  .delta h3{margin:18px 0 8px;font-size:15px}
  .dgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px}
  .dcard{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px 12px}
  .dcard .v{font-size:18px;font-weight:600}
  .pos{color:var(--pos)} .neg{color:var(--neg)}
  footer{color:var(--muted);font-size:12px;padding:18px 24px;border-top:1px solid var(--line)}
</style>
</head>
<body>
<header>
  <h1>Texas Home Health Market Explorer</h1>
  <div class="sub">HHSC HCSSA directory (2026-03-01 snapshot) · ACS 2024 5-Yr S0101 · OMB 2023 core-based statistical areas (CBSAs).
  Full HCSSA directory shown; home health tiers drive all density and caseload metrics.
  Counts are distinct agencies (unique license number), recomputed at each geography level — never summed across levels.</div>
</header>
<div class="wrap">
  <div class="cards" id="cards"></div>

  <div class="controls">
    <div class="seg" id="view">
      <button data-v="cbsa" class="on">Metros / CBSA</button>
      <button data-v="county">Counties</button>
    </div>
    <input type="search" id="q" placeholder="Filter by name…">
    <div class="seg" id="metric">
      <button data-m="cert_per_10k_sr" class="on">per 10K seniors</button>
      <button data-m="agencies_per_100k">per 100K pop</button>
    </div>
    <label class="chk"><input type="checkbox" id="metroonly" checked> Metros only</label>
    <label class="chk"><input type="checkbox" id="i35only"> I-35 corridor only</label>
    <span class="i35key" title="I-35 corridor"><span class="i35bar">▎</span> I-35 corridor</span>
    <span class="dim" id="count"></span>
  </div>
  <div class="note key" id="bench"></div>

  <div class="tablewrap"><table id="tbl"><thead></thead><tbody></tbody></table></div>
  <div class="note" id="note"></div>

__MAPSECTION__
  <div class="delta">
    <h3>June 2026 market dynamics (vs March)</h3>
    <div class="dgrid" id="delta"></div>
  </div>
</div>
<footer>
  Densities: per 10K seniors (65+) is the headline metric. County rows count
  “agencies with a location in county”; a multi-county agency counts once per
  county but only once per metro, so county rows do not sum to metro totals.
  “Clients (census)” = sum of self-reported Current client census across reporting
  locations in the geography; the small % is the location-level reporting rate
  (~31% of locations statewide are blank), so totals are a reporting-bounded lower
  read of patients treated.
</footer>

<script>
const DATA = __DATA__;
const fmt = n => n.toLocaleString();
const f1 = n => n.toFixed(1);
const f2 = n => n.toFixed(2);

// ---- summary cards ----
const s = DATA.summary;
const hhCert = s.tier_distinct["Medicare-certified HH"];
const hhLic = s.tier_distinct["Licensed-only HH"];
const hhAgencies = hhCert + hhLic;
const cards = [
  {k:"Home health agencies", v:fmt(hhAgencies),
   sub:fmt(hhCert)+" Medicare-certified · "+fmt(hhLic)+" licensed-only",
   ctx:"within "+fmt(s.agencies)+" licensed agencies / "+fmt(s.locations)+" locations in the full HCSSA directory"},
  {k:"Certified HH", v:fmt(hhCert), sub:s.state_cert_per_10k+" per 10K seniors"},
  {k:"Texas 65+", v:fmt(s.texas_seniors), sub:s.senior_share+"% of population"},
  {k:"Certified home health patients", v:fmt(s.tier_census["Medicare-certified HH"]),
   sub:Math.round(s.tier_reporting["Medicare-certified HH"])+"% of certified locations reporting",
   ctx:"all licensed service types: "+fmt(s.census_lower)+"–"+fmt(s.census_upper)+" reported clients (lower–upper bound)"},
  {k:"Whitespace", v:s.whitespace_counties+" counties",
   sub:"0 licensed locations (any service type) · "+s.whitespace_in_metro+" inside metros"},
];
document.getElementById('bench').innerHTML =
  `<span class="below">●</span> below state benchmark — ${f2(s.state_cert_per_10k)} certified per 10K seniors (neutral = at or above)`;

document.getElementById('cards').innerHTML = cards.map(c =>
  `<div class="card"><div class="k">${c.k}</div><div class="v">${c.v}</div>`
  + (c.sub?`<div class="sub2">${c.sub}</div>`:'')
  + (c.ctx?`<div class="ctx">${c.ctx}</div>`:'')
  + `</div>`
).join('');

// ---- table ----
const COLS = {
  cbsa: [
    ["cbsa","CBSA / Metro",false],["type","Type",false],
    ["agencies","Agencies",true],["certified","Certified",true],
    ["licensed_only","Lic-only",true],["hospice","Hospice",true],["pas","PAS",true],
    ["seniors","Seniors 65+",true],["__metric","Density",true],
    ["census","All-type clients",true,"Clients, all licensed service types (census)"],
    ["cert_census","Certified clients",true,"Clients in Medicare-certified home health (census)"],
    ["avg_clients_certified","Per cert. agency",true,"Clients per certified agency (certified clients ÷ certified agencies)"],
  ],
  county: [
    ["county","County",false],["cbsa","CBSA",false],["type","Type",false],
    ["agencies","Agencies",true],["certified","Certified",true],
    ["licensed_only","Lic-only",true],["hospice","Hospice",true],["pas","PAS",true],
    ["locations","Locations",true],["seniors","Seniors 65+",true],["__metric","Density",true],
    ["census","All-type clients",true,"Clients, all licensed service types (census)"],
  ],
};
let view='cbsa', metric='cert_per_10k_sr', sortKey='__metric', sortDir=1, i35only=false, metroOnly=true, q='';
const BENCH = s.state_cert_per_10k;
const TIGHT = new Set(['agencies','certified','licensed_only','hospice','pas','locations','seniors']);

function rows(){
  let r = DATA[view].slice();
  if(metroOnly) r = r.filter(x=>x.type==='Metro');
  if(i35only && view==='cbsa') r = r.filter(x=>x.i35);
  if(q){ const t=q.toLowerCase(); r=r.filter(x=>(x.cbsa+' '+(x.county||'')).toLowerCase().includes(t)); }
  const k = sortKey==='__metric'?metric:sortKey;
  r.sort((a,b)=>{ let av=a[k],bv=b[k];
    if(typeof av==='string') return sortDir*av.localeCompare(bv);
    return sortDir*((av-bv)||0); });
  return r;
}
function metricVal(x){ return metric==='cert_per_10k_sr'?f2(x.cert_per_10k_sr):f2(x.agencies_per_100k); }
function metricLabel(){ return metric==='cert_per_10k_sr'?'Cert / 10K seniors':'Agencies / 100K pop'; }

function render(){
  const cols=COLS[view];
  const thead=document.querySelector('#tbl thead');
  thead.innerHTML='<tr>'+cols.map(c=>{
    const on=(sortKey===c[0]||(c[0]==='__metric'&&sortKey==='__metric'))?'on':'';
    const arrow=(sortKey===c[0])?(sortDir<0?' ▾':' ▴'):'';
    const label=c[0]==='__metric'?metricLabel():c[1];
    const full=c[3]||(c[0]==='__metric'?metricLabel():c[1]);
    const cls=[on, TIGHT.has(c[0])?'tight':''].filter(Boolean).join(' ');
    return `<th class="${cls}" data-k="${c[0]}" title="${full}">${label}${arrow}</th>`;
  }).join('')+'</tr>';
  thead.querySelectorAll('th').forEach(th=>th.onclick=()=>{
    const k=th.dataset.k;
    if(sortKey===k) sortDir*=-1; else {sortKey=k; sortDir=(k==='cbsa'||k==='county'||k==='type')?1:-1;}
    render();
  });
  const r=rows();
  const body=cols.map(()=>0);
  document.querySelector('#tbl tbody').innerHTML=r.map(x=>{
    const tds=cols.map(c=>{
      const t=TIGHT.has(c[0])?' tight':'';
      if(c[0]==='__metric'){
        const below = metric==='cert_per_10k_sr' && x.cert_per_10k_sr < BENCH;
        return `<td class="${below?'below':''}">${below?'● ':''}${metricVal(x)}</td>`;
      }
      if(c[0]==='type') return `<td><span class="pill ${x.type}">${x.type}</span></td>`;
      let v=x[c[0]];
      if(c[0]==='cbsa'||c[0]==='county') return `<td class="name" title="${(v||'').replace(/"/g,'&quot;')}">${v||'<span class=dim>—</span>'}</td>`;
      if(c[0]==='avg_clients_certified') return `<td>${v?f1(v):'<span class=dim>—</span>'}</td>`;
      if(c[0]==='census') return `<td>${v?fmt(v):'<span class=dim>—</span>'}<span class="dim" style="font-size:11px"> ${x.census_rate?(x.census_rate+'%'):''}</span></td>`;
      if(c[0]==='cert_census') return `<td>${v?fmt(v):'<span class=dim>—</span>'}</td>`;
      return `<td class="${t.trim()}">${typeof v==='number'?fmt(v):v}</td>`;
    }).join('');
    return `<tr class="${x.i35?'i35':''}">${tds}</tr>`;
  }).join('');
  document.getElementById('count').textContent=r.length+' rows';
  document.getElementById('note').innerHTML = view==='cbsa'
    ? 'Orange edge = I-35 corridor metro. Metro totals do <b>not</b> sum to the statewide '
      +fmt(s.agencies)+' distinct agencies — counts are recomputed independently at each level.'
    : '“Agencies” = distinct License No with ≥1 location in the county.';
}

// ---- controls ----
document.querySelectorAll('#view button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('#view button').forEach(x=>x.classList.remove('on'));
  b.classList.add('on'); view=b.dataset.v;
  if(sortKey==='avg_clients_certified'&&view==='county') sortKey='agencies';
  render();
});
document.querySelectorAll('#metric button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('#metric button').forEach(x=>x.classList.remove('on'));
  b.classList.add('on'); metric=b.dataset.m; render();
});
document.getElementById('q').oninput=e=>{q=e.target.value;render();};
document.getElementById('metroonly').onchange=e=>{metroOnly=e.target.checked;render();};
document.getElementById('i35only').onchange=e=>{i35only=e.target.checked;render();};

// ---- june delta ----
const j=s.june, tierName={"PAS only":"PAS","Licensed-only HH":"Lic-only","Hospice":"Hospice","Medicare-certified HH":"Certified"};
const sign=n=>(n>0?'+':'')+n;
const dcards=[
  ["June locations",fmt(j.june_locations),''],
  ["June agencies",fmt(j.june_distinct),''],
  ["New licenses",fmt(j.n_new),'pos'],
  ["Dropped",fmt(j.n_dropped),'neg'],
  ["Net change",sign(j.net),j.net>=0?'pos':'neg'],
];
let dh=dcards.map(c=>`<div class="dcard"><div class="k dim">${c[0]}</div><div class="v ${c[2]}">${c[1]}</div></div>`).join('');
dh+=DATA.tiers.map(t=>{
  const nn=j.net_by_tier[t]||0;
  return `<div class="dcard"><div class="k dim">Net distinct · ${tierName[t]}</div>`
    +`<div class="v ${nn>=0?'pos':'neg'}">${sign(nn)}</div></div>`;
}).join('');
document.getElementById('delta').innerHTML=dh;

render();
</script>
</body>
</html>"""


def main():
    b = build()
    data = assemble(b)
    html = render_html(data)
    # Self-contained: data is inlined JSON, no external assets. Written under the
    # descriptive name and as index.html (the GitHub Pages root entry point).
    for name in ("texas_hha_market_explorer.html", "index.html"):
        (config.ROOT / name).write_text(html)
    print(f"Wrote texas_hha_market_explorer.html + index.html ({len(html):,} bytes) — "
          f"{len(data['cbsa'])} CBSA rows, {len(data['county'])} county rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
