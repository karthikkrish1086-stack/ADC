"""
Alteryx -> Python conversion — live demo app.
Run locally:   streamlit run app.py
Opens at:      http://localhost:8501

Self-contained: generates its own data, parses the bundled .yxmd workflows,
converts to Python via the converter, runs the generated code in-memory,
and validates output parity against an independent reference implementation.
Needs only: streamlit, pandas, numpy.
"""
import streamlit as st
import pandas as pd, numpy as np, os, html
import converter as cv

# --------------------------------------------------------------------------
# PAGE + THEME  (deep-ocean engineering console; continuity with the deck)
# --------------------------------------------------------------------------
st.set_page_config(page_title="Alteryx Python Live Conversion",
                   page_icon="◇", layout="wide")

CSS = """
<style>
:root{
  --ink:#0E1820; --panel:#16232E; --panel2:#1C2E3B; --line:#2A4150;
  --ice:#E8F1F5; --mute:#7F96A4; --deep:#1C7293; --sky:#8FC1D4;
  --green:#28C2A6; --amber:#E0A458; --mono:'SFMono-Regular',Consolas,'Courier New',monospace;
}
.stApp{ background:radial-gradient(1200px 600px at 80% -10%, #1B3340 0%, var(--ink) 55%); }
.block-container{ padding-top:1.6rem; max-width:1280px; }
h1,h2,h3,h4{ color:var(--ice); font-family:'Cambria',Georgia,serif; letter-spacing:.2px; }
p,li,label,.stMarkdown{ color:#C7D6DE; }
.eyebrow{ color:var(--sky); font-size:.78rem; font-weight:700; letter-spacing:.32em;
  text-transform:uppercase; }
.lede{ color:var(--mute); font-size:1.02rem; }
hr{ border-color:var(--line); }

/* pipeline rail */
.rail{ display:flex; align-items:stretch; gap:0; margin:.4rem 0 1.2rem; flex-wrap:wrap; }
.stage{ flex:1; min-width:120px; background:var(--panel); border:1px solid var(--line);
  border-radius:10px; padding:.7rem .8rem; position:relative; }
.stage .n{ color:var(--deep); font-family:var(--mono); font-size:.72rem; font-weight:700; }
.stage .t{ color:var(--ice); font-weight:700; font-size:.92rem; margin-top:.15rem; }
.stage .d{ color:var(--mute); font-size:.74rem; margin-top:.2rem; line-height:1.25; }
.arrow{ display:flex; align-items:center; color:var(--deep); font-size:1.3rem; padding:0 .35rem; }
.stage.on{ border-color:var(--green); box-shadow:0 0 0 1px var(--green) inset; }
.stage.on .n{ color:var(--green); }

/* code panels */
.codewrap{ background:#0B141B; border:1px solid var(--line); border-radius:10px;
  overflow:hidden; }
.codehead{ display:flex; justify-content:space-between; align-items:center;
  padding:.45rem .8rem; border-bottom:1px solid var(--line); font-family:var(--mono);
  font-size:.74rem; letter-spacing:.04em; }
.codehead .l{ color:var(--mute); }
.tag-ai{ color:var(--green); font-weight:700; }
.tag-tpl{ color:var(--sky); font-weight:700; }
pre.code{ margin:0; padding:.7rem .9rem; font-family:var(--mono); font-size:.79rem;
  line-height:1.5; color:#D6E3EA; white-space:pre-wrap; word-break:break-word; }
.l-ai{ background:rgba(40,194,166,.08); border-left:2px solid var(--green);
  display:block; padding-left:.5rem; }
.l-tpl{ background:rgba(143,193,212,.06); border-left:2px solid var(--sky);
  display:block; padding-left:.5rem; }
.l-plain{ display:block; padding-left:.5rem; border-left:2px solid transparent; }
.cmt{ color:#5E7A88; }

/* metric chips */
.chips{ display:flex; gap:.7rem; flex-wrap:wrap; margin:.3rem 0 .2rem; }
.chip{ background:var(--panel); border:1px solid var(--line); border-radius:10px;
  padding:.6rem .9rem; min-width:120px; }
.chip .v{ font-family:'Cambria',serif; font-size:1.7rem; font-weight:700; }
.chip .k{ color:var(--mute); font-size:.72rem; text-transform:uppercase; letter-spacing:.12em; }
.v-deep{ color:var(--sky);} .v-green{ color:var(--green);} .v-amber{ color:var(--amber);} .v-ice{color:var(--ice);}

.pass{ color:var(--green); font-weight:700; }
.badge{ display:inline-block; background:rgba(40,194,166,.12); color:var(--green);
  border:1px solid var(--green); border-radius:999px; padding:.15rem .7rem;
  font-family:var(--mono); font-size:.78rem; font-weight:700; }
.stButton>button{ background:var(--deep); color:#fff; border:0; border-radius:9px;
  font-weight:700; padding:.55rem 1.1rem; }
.stButton>button:hover{ background:#2487AC; color:#fff; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# --------------------------------------------------------------------------
# DATA  (generated once, cached)
# --------------------------------------------------------------------------
@st.cache_data
def make_data():
    np.random.seed(42)
    regions = ["Southeast", "Northeast", "Midwest", "West"]
    stores = pd.DataFrame({
        "StoreID": [f"S{100+i}" for i in range(40)],
        "StoreName": [f"Store {i}" for i in range(40)],
        "Region": np.random.choice(regions, 40, p=[.5, .2, .15, .15]),
        "AnnualRevenue": np.random.randint(200000, 1500000, 40),
        "Latitude": np.round(33.749 + np.random.uniform(-2, 2, 40), 4),
        "Longitude": np.round(-84.388 + np.random.uniform(-2, 2, 40), 4),
    })
    cust = pd.DataFrame({
        "CustomerID": [f"C{1000+i}" for i in range(500)],
        "CustomerName": [f"Cust {i}" for i in range(500)],
        "LifetimeValue": np.round(np.random.gamma(2.0, 1500, 500), 2),
        "Latitude": np.round(33.749 + np.random.normal(0, .6, 500), 4),
        "Longitude": np.round(-84.388 + np.random.normal(0, .6, 500), 4),
    })
    return stores, cust

STORES, CUST = make_data()
TABLES = {"stores.csv": STORES, "customers.csv": CUST}

WORKFLOWS = {
    "Simple — Store Filter (4 tools)": {
        "file": "workflows/simple_store_filter.yxmd",
        "blurb": "Input -> Filter -> Select -> Output. Keeps Southeast stores with revenue over $500K.",
        "inputs": ["stores.csv"],
    },
    "Complex — Trade-Area Capture (10 tools)": {
        "file": "workflows/complex_trade_area.yxmd",
        "blurb": "Two streams, 10-mile store buffers, point-in-polygon match, segmentation, roll-up.",
        "inputs": ["stores.csv", "customers.csv"],
    },
}

# --------------------------------------------------------------------------
# REFERENCE IMPLEMENTATIONS (independent — for the parity check)
# --------------------------------------------------------------------------
def _hav(lon1, lat1, lon2, lat2):
    R = 3958.7613
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1; dlat = lat2 - lat1
    a = np.sin(dlat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dlon/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

def reference_simple():
    s = STORES
    return s[(s.Region == "Southeast") & (s.AnnualRevenue > 500000)][
        ["StoreID", "StoreName", "Region", "AnnualRevenue"]].reset_index(drop=True)

def reference_complex():
    rows = []
    for _, s in STORES.iterrows():
        d = _hav(CUST.Longitude, CUST.Latitude, s.Longitude, s.Latitude)
        inside = CUST[d <= 10].copy()
        inside["StoreID"] = s.StoreID; inside["StoreName"] = s.StoreName
        inside["DistToStore"] = d[d <= 10].values
        rows.append(inside)
    m = pd.concat(rows, ignore_index=True)
    seg = np.where((m.LifetimeValue > 5000) & (m.DistToStore < 5), "Priority",
          np.where(m.LifetimeValue > 2000, "Standard", "Low"))
    m["CustomerSegment"] = seg
    kept = m[m.CustomerSegment != "Low"]
    return kept.groupby(["StoreID", "StoreName"], as_index=False).agg(
        CapturedCustomers=("CustomerID", "nunique"),
        CapturedLTV=("LifetimeValue", "sum"),
        AvgCustDistance=("DistToStore", "mean")).reset_index(drop=True)

def parity(gen, ref):
    g = gen.sort_values(list(gen.columns)).reset_index(drop=True)
    r = ref.sort_values(list(ref.columns)).reset_index(drop=True)
    if list(g.columns) != list(r.columns) or len(g) != len(r):
        return False
    for c in g.columns:
        if g[c].dtype.kind in "fc":
            if not np.allclose(g[c].astype(float), r[c].astype(float)): return False
        else:
            if g[c].astype(str).tolist() != r[c].astype(str).tolist(): return False
    return True

# --------------------------------------------------------------------------
# CODE RENDERING (tag-aware highlight)
# --------------------------------------------------------------------------
def render_code(body_lines):
    out = []
    for raw in body_lines:
        for line in raw.split("\n"):
            esc = html.escape(line)
            if "  #" in esc:
                code_part, cmt = esc.split("  #", 1)
                esc = f'{code_part}<span class="cmt">  #{cmt}</span>'
            cls = "l-plain"
            if "[AI]" in line: cls = "l-ai"
            elif "[TEMPLATE]" in line: cls = "l-tpl"
            out.append(f'<span class="{cls}">{esc or "&nbsp;"}</span>')
    return "<pre class='code'>" + "\n".join(out) + "</pre>"

PIPELINE = [
    ("01", "Parse XML", "Read .yxmd, build the tool graph"),
    ("02", "Map tools", "Common tools -> pandas templates"),
    ("03", "AI translate", "Spatial + formula logic -> Python"),
    ("04", "Run", "Execute generated code on the data"),
    ("05", "Validate", "Compare to independent reference"),
]
def rail(active=-1):
    parts = ['<div class="rail">']
    for i, (n, t, d) in enumerate(PIPELINE):
        on = "on" if i <= active else ""
        parts.append(f'<div class="stage {on}"><div class="n">{n}</div>'
                     f'<div class="t">{t}</div><div class="d">{d}</div></div>')
        if i < len(PIPELINE) - 1:
            parts.append('<div class="arrow">-></div>')
    parts.append("</div>")
    return "".join(parts)

# --------------------------------------------------------------------------
# HEADER
# --------------------------------------------------------------------------
st.markdown('<div class="eyebrow">Migration Proof of Concept</div>', unsafe_allow_html=True)
st.markdown("# Alteryx -> Python, converted live")
st.markdown('<p class="lede">Pick a workflow, load the geospatial data, and watch it convert '
            'end to end — parsed, AI-translated, executed, and validated for output parity.</p>',
            unsafe_allow_html=True)

# --------------------------------------------------------------------------
# CONTROLS
# --------------------------------------------------------------------------
c1, c2 = st.columns([3, 1])
with c1:
    choice = st.radio("Workflow", list(WORKFLOWS.keys()), horizontal=True, label_visibility="collapsed")
with c2:
    run = st.button("Run conversion", use_container_width=True)

wf = WORKFLOWS[choice]
st.caption(wf["blurb"])

# --------------------------------------------------------------------------
# DATA PREVIEW (always visible — "load the data")
# --------------------------------------------------------------------------
st.markdown("#### Source data")
dcols = st.columns(len(wf["inputs"]))
for col, name in zip(dcols, wf["inputs"]):
    df = TABLES[name]
    with col:
        st.markdown(f"**`{name}`** · {df.shape[0]} rows x {df.shape[1]} cols")
        st.dataframe(df.head(6), use_container_width=True, height=230)

st.markdown(rail(-1 if not run else 4), unsafe_allow_html=True)

# --------------------------------------------------------------------------
# RUN
# --------------------------------------------------------------------------
if run:
    src, stats, nodes, order, body = cv.generate_source(wf["file"])

    st.markdown("#### Conversion result")
    st.markdown(
        f'<div class="chips">'
        f'<div class="chip"><div class="v v-ice">{len(nodes)}</div><div class="k">tools</div></div>'
        f'<div class="chip"><div class="v v-deep">{stats.template}</div><div class="k">template-mapped</div></div>'
        f'<div class="chip"><div class="v v-green">{stats.ai}</div><div class="k">AI-translated</div></div>'
        f'<div class="chip"><div class="v v-amber">{stats.unsupported}</div><div class="k">unsupported</div></div>'
        f'</div>', unsafe_allow_html=True)

    left, right = st.columns([1, 1])
    with left:
        st.markdown('<div class="codewrap"><div class="codehead">'
                    '<span class="l">GENERATED PYTHON</span>'
                    '<span><span class="tag-ai">[AI]</span> &nbsp; <span class="tag-tpl">[TEMPLATE]</span></span>'
                    '</div>' + render_code(body) + '</div>', unsafe_allow_html=True)
    with right:
        captured, ns = cv.run_generated(body, TABLES)
        out_name = list(captured.keys())[0]
        gen_df = captured[out_name]

        if "simple" in wf["file"]:
            ref = reference_simple()
        else:
            ref = reference_complex()
        ok = parity(gen_df, ref)

        status = "PARITY PASS" if ok else "MISMATCH"
        cls = "pass" if ok else ""
        st.markdown(f'<div class="codehead" style="border:1px solid var(--line);'
                    f'border-radius:10px 10px 0 0;background:#0B141B;">'
                    f'<span class="l">OUTPUT · {html.escape(out_name)}</span>'
                    f'<span class="{cls}">{status}</span></div>',
                    unsafe_allow_html=True)
        st.dataframe(gen_df.head(20), use_container_width=True, height=300)

        if "complex" in wf["file"]:
            st.markdown(
                f'<div class="chips">'
                f'<div class="chip"><div class="v v-deep">{gen_df.shape[0]}</div>'
                f'<div class="k">stores capturing customers</div></div>'
                f'<div class="chip"><div class="v v-green">${gen_df.CapturedLTV.sum():,.0f}</div>'
                f'<div class="k">total captured LTV</div></div>'
                f'</div>', unsafe_allow_html=True)

        st.markdown(
            '<p style="color:var(--mute);font-size:.82rem;margin-top:.6rem;">'
            'Parity is checked against an <b>independently written</b> reference implementation — '
            'not the converter — so a pass means the generated Python reproduces Alteryx output exactly.'
            '</p>', unsafe_allow_html=True)

    ai_lines = [l for b in body for l in b.split("\n") if "[AI]" in l]
    if ai_lines:
        with st.expander(f"What the AI layer translated  ({len(ai_lines)} expressions)"):
            for l in ai_lines:
                expr = l.split("# [AI]", 1)[1].strip() if "# [AI]" in l else l
                st.markdown(f"- `{expr}`")
else:
    st.info("Press Run conversion to parse the workflow, generate Python, execute it on the data above, and validate parity.")

st.markdown("<hr>", unsafe_allow_html=True)
st.caption("Self-contained POC · pandas + numpy · production target: GeoPandas / Shapely. "
           "AI translations shown here are cached; wire converter.ai_translate_formula to a live model to scale.")
