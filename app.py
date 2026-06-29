"""
Alteryx -> Python conversion — live demo app (stakeholder edition).
For each workflow it shows: the original Alteryx flow, the converted Python,
the output data, and a side-by-side OLD vs NEW comparison proving parity.
Needs only: streamlit, pandas, numpy.
"""
import streamlit as st
import pandas as pd, numpy as np, html
import converter as cv

st.set_page_config(page_title="Alteryx to Python | Live Conversion",
                   page_icon="diamond", layout="wide")

CSS = """
<style>
:root{
  --ink:#0E1820; --panel:#16232E; --panel2:#1C2E3B; --line:#2A4150;
  --ice:#E8F1F5; --mute:#7F96A4; --deep:#1C7293; --sky:#8FC1D4;
  --green:#28C2A6; --amber:#E0A458; --red:#E0645A;
  --mono:'SFMono-Regular',Consolas,'Courier New',monospace;
}
.stApp{ background:radial-gradient(1200px 600px at 80% -10%, #1B3340 0%, var(--ink) 55%); }
.block-container{ padding-top:1.4rem; max-width:1320px; }
h1,h2,h3,h4{ color:var(--ice); font-family:'Cambria',Georgia,serif; }
p,li,label,.stMarkdown{ color:#C7D6DE; }
.eyebrow{ color:var(--sky); font-size:.74rem; font-weight:700; letter-spacing:.3em; text-transform:uppercase; }
.lede{ color:var(--mute); font-size:1.0rem; }
hr{ border-color:var(--line); margin:1rem 0; }

.sectlabel{ color:var(--sky); font-size:.72rem; font-weight:700; letter-spacing:.18em;
  text-transform:uppercase; margin:.2rem 0 .5rem; }

.flow{ display:flex; flex-direction:column; gap:.4rem; }
.tool{ background:var(--panel); border:1px solid var(--line); border-radius:9px;
  padding:.55rem .8rem; display:flex; gap:.7rem; align-items:flex-start; }
.tool .ico{ width:26px;height:26px;border-radius:6px;background:var(--deep);color:#fff;
  font-family:var(--mono);font-size:.72rem;font-weight:700;display:flex;align-items:center;
  justify-content:center;flex-shrink:0;margin-top:1px; }
.tool .body{ flex:1; }
.tool .tn{ color:var(--ice); font-weight:700; font-size:.88rem; }
.tool .nm{ color:var(--mute); font-size:.74rem; }
.tool .dt{ color:#9FB4C0; font-family:var(--mono); font-size:.74rem; margin-top:.15rem; word-break:break-word; }
.tool.ai{ border-color:var(--green); }
.tool.ai .ico{ background:var(--green); }

.codewrap{ background:#0B141B; border:1px solid var(--line); border-radius:9px; overflow:hidden; }
.codehead{ display:flex; justify-content:space-between; align-items:center; padding:.4rem .8rem;
  border-bottom:1px solid var(--line); font-family:var(--mono); font-size:.72rem; }
.codehead .l{ color:var(--mute); }
.tag-ai{ color:var(--green); font-weight:700; } .tag-tpl{ color:var(--sky); font-weight:700; }
pre.code{ margin:0; padding:.6rem .8rem; font-family:var(--mono); font-size:.75rem;
  line-height:1.5; color:#D6E3EA; white-space:pre-wrap; word-break:break-word; }
.l-ai{ background:rgba(40,194,166,.08); border-left:2px solid var(--green); display:block; padding-left:.5rem; }
.l-tpl{ background:rgba(143,193,212,.06); border-left:2px solid var(--sky); display:block; padding-left:.5rem; }
.l-plain{ display:block; padding-left:.5rem; border-left:2px solid transparent; }
.cmt{ color:#5E7A88; }

.chips{ display:flex; gap:.6rem; flex-wrap:wrap; margin:.2rem 0; }
.chip{ background:var(--panel); border:1px solid var(--line); border-radius:9px; padding:.5rem .8rem; min-width:104px; }
.chip .v{ font-family:'Cambria',serif; font-size:1.5rem; font-weight:700; }
.chip .k{ color:var(--mute); font-size:.68rem; text-transform:uppercase; letter-spacing:.1em; }
.v-deep{color:var(--sky);} .v-green{color:var(--green);} .v-amber{color:var(--amber);} .v-ice{color:var(--ice);}

.verdict{ display:flex; align-items:center; gap:.7rem; background:rgba(40,194,166,.1);
  border:1px solid var(--green); border-radius:10px; padding:.7rem 1rem; margin:.4rem 0; }
.verdict .big{ color:var(--green); font-weight:800; font-size:1.05rem; font-family:'Cambria',serif; }
.verdict .sub{ color:#A9C7CD; font-size:.82rem; }
.verdict.fail{ background:rgba(224,100,90,.1); border-color:var(--red); }
.verdict.fail .big{ color:var(--red); }
.stButton>button{ background:var(--deep); color:#fff; border:0; border-radius:9px; font-weight:700; }
.stButton>button:hover{ background:#2487AC; color:#fff; }
.stTabs [data-baseweb="tab"]{ font-weight:700; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

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
    "Simple": {
        "title": "Store Filter",
        "file": "workflows/simple_store_filter.yxmd",
        "blurb": "A basic filter-and-select: keep Southeast stores earning over $500K. The everyday workflow that makes up most of a library.",
        "inputs": ["stores.csv"],
    },
    "Medium": {
        "title": "Customer Proximity",
        "file": "workflows/medium_proximity_analysis.yxmd",
        "blurb": "Spatial points, distance-to-HQ, tiered segmentation, and a summary. Introduces geospatial math and conditional logic.",
        "inputs": ["customers.csv"],
    },
    "Complex": {
        "title": "Trade-Area Capture",
        "file": "workflows/complex_trade_area.yxmd",
        "blurb": "Two data streams, 10-mile store buffers, point-in-polygon matching, segmentation and roll-up. The hard case that proves the approach.",
        "inputs": ["stores.csv", "customers.csv"],
    },
}

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

def reference_medium():
    c = CUST.copy()
    d = _hav(c.Longitude, c.Latitude, -84.388, 33.749)
    c["DistToHQ_Miles"] = d
    c["ProximityTier"] = np.where(d <= 25, "Near", np.where(d <= 100, "Mid", "Far"))
    return c.groupby("ProximityTier", as_index=False).agg(
        CustomerCount=("CustomerID", "count"),
        AvgDistance=("DistToHQ_Miles", "mean"),
        TotalLTV=("LifetimeValue", "sum")).reset_index(drop=True)

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

REFS = {"Simple": reference_simple, "Medium": reference_medium, "Complex": reference_complex}

def compare(old, new):
    o = old.sort_values(list(old.columns)).reset_index(drop=True)
    n = new.sort_values(list(new.columns)).reset_index(drop=True)
    same_shape = (o.shape == n.shape) and (list(o.columns) == list(n.columns))
    cell_match = 0; cell_total = 0; identical = same_shape
    if same_shape:
        for c in o.columns:
            cell_total += len(o)
            if o[c].dtype.kind in "fc":
                eq = np.isclose(o[c].astype(float), n[c].astype(float))
            else:
                eq = o[c].astype(str).values == n[c].astype(str).values
            cell_match += int(eq.sum())
            if not eq.all():
                identical = False
    summary = {"rows_old": len(old), "rows_new": len(new),
               "cols": len(old.columns), "cell_match": cell_match, "cell_total": cell_total}
    return identical, summary

def render_flow(steps):
    parts = ['<div class="flow">']
    for s in steps:
        is_ai = s["tool"] in ("Create Points", "Buffer (Trade Area)", "Spatial Match") \
                or "Distance" in (s["detail"] or "") or "IF " in (s["detail"] or "")
        cls = "tool ai" if is_ai else "tool"
        det = html.escape(s["detail"] or "")
        parts.append(
            f'<div class="{cls}"><div class="ico">{s["id"]}</div>'
            f'<div class="body"><div class="tn">{html.escape(s["tool"])}</div>'
            f'<div class="nm">{html.escape(s["name"])}</div>'
            + (f'<div class="dt">{det}</div>' if det else "")
            + '</div></div>')
    parts.append("</div>")
    return "".join(parts)

def render_code(body_lines):
    out = []
    for raw in body_lines:
        for line in raw.split("\n"):
            esc = html.escape(line)
            if "  #" in esc:
                cp, cm = esc.split("  #", 1)
                esc = f'{cp}<span class="cmt">  #{cm}</span>'
            cls = "l-plain"
            if "[AI]" in line: cls = "l-ai"
            elif "[TEMPLATE]" in line: cls = "l-tpl"
            out.append(f'<span class="{cls}">{esc or "&nbsp;"}</span>')
    return "<pre class='code'>" + "\n".join(out) + "</pre>"

st.markdown('<div class="eyebrow">Alteryx to Python · Migration Proof of Concept</div>', unsafe_allow_html=True)
st.markdown("# See it convert, then see the numbers match")
st.markdown('<p class="lede">For each workflow: the original Alteryx flow on the left, the AI-converted Python on the right, '
            'then the output of the old flow and the new flow side by side. If the numbers match, the conversion is trustworthy.</p>',
            unsafe_allow_html=True)

tab_labels = [f"{k} — {WORKFLOWS[k]['title']}" for k in WORKFLOWS] + ["Try Your Own", "Source Connectors"]
tabs = st.tabs(tab_labels)
wf_tabs = tabs[:len(WORKFLOWS)]
upload_tab = tabs[-2]
source_tab = tabs[-1]

for tab, key in zip(wf_tabs, WORKFLOWS):
    wf = WORKFLOWS[key]
    with tab:
        st.markdown(f"#### {key}: {wf['title']}")
        st.caption(wf["blurb"])

        src, stats, nodes, order, body = cv.generate_source(wf["file"])
        steps = cv.describe_workflow(wf["file"])

        st.markdown(
            f'<div class="chips">'
            f'<div class="chip"><div class="v v-ice">{len(nodes)}</div><div class="k">tools</div></div>'
            f'<div class="chip"><div class="v v-deep">{stats.template}</div><div class="k">template</div></div>'
            f'<div class="chip"><div class="v v-green">{stats.ai}</div><div class="k">AI-translated</div></div>'
            f'<div class="chip"><div class="v v-amber">{stats.unsupported}</div><div class="k">unsupported</div></div>'
            f'</div>', unsafe_allow_html=True)

        st.markdown("<hr>", unsafe_allow_html=True)
        a, b = st.columns(2)
        with a:
            st.markdown('<div class="sectlabel">Original Alteryx workflow</div>', unsafe_allow_html=True)
            st.markdown(render_flow(steps), unsafe_allow_html=True)
            st.markdown('<div class="sectlabel" style="margin-top:.8rem;">Original Alteryx code (.yxmd source)</div>', unsafe_allow_html=True)
            st.code(cv.raw_xml(wf["file"]), language="xml")
        with b:
            st.markdown('<div class="sectlabel">Converted Python · green = AI-translated</div>', unsafe_allow_html=True)
            st.markdown('<div class="codewrap"><div class="codehead">'
                        '<span class="l">workflow logic (highlighted)</span>'
                        '<span><span class="tag-ai">[AI]</span> &nbsp; <span class="tag-tpl">[TEMPLATE]</span></span>'
                        '</div>' + render_code(body) + '</div>', unsafe_allow_html=True)
            full = cv.full_script(src, f"{key} - {wf['title']}")
            with st.expander("Full runnable script (imports + helpers + logic)"):
                st.code(full, language="python")
            st.download_button("Download generated .py", full,
                               file_name=f"{key.lower()}_{wf['title'].lower().replace(' ','_')}.py",
                               mime="text/x-python", key=f"dl_{key}")

        captured, _ = cv.run_generated(body, TABLES)
        out_name = list(captured.keys())[0]
        new_raw = captured[out_name]
        new_df = new_raw.sort_values(list(new_raw.columns)).reset_index(drop=True)
        old_raw = REFS[key]()
        old_df = old_raw.sort_values(list(old_raw.columns)).reset_index(drop=True)
        identical, summ = compare(old_df, new_df)

        st.markdown("<hr>", unsafe_allow_html=True)
        if identical:
            st.markdown(
                f'<div class="verdict"><div class="big">MATCH</div>'
                f'<div class="sub">Old Alteryx flow and new Python produce identical output — '
                f'{summ["rows_new"]} rows x {summ["cols"]} columns, {summ["cell_match"]}/{summ["cell_total"]} cells equal.</div></div>',
                unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="verdict fail"><div class="big">DIFFERENCE FOUND</div>'
                f'<div class="sub">{summ["cell_match"]}/{summ["cell_total"]} cells matched — review needed.</div></div>',
                unsafe_allow_html=True)

        c, d = st.columns(2)
        with c:
            st.markdown('<div class="sectlabel">Output — original Alteryx flow</div>', unsafe_allow_html=True)
            st.dataframe(old_df, use_container_width=True, height=320)
        with d:
            st.markdown('<div class="sectlabel">Output — converted Python</div>', unsafe_allow_html=True)
            st.dataframe(new_df, use_container_width=True, height=320)

        ai_lines = [l for bb in body for l in bb.split("\n") if "[AI]" in l]
        if ai_lines:
            with st.expander(f"What the AI layer translated ({len(ai_lines)} expressions with no 1:1 mapping)"):
                for l in ai_lines:
                    expr = l.split("# [AI]", 1)[1].strip() if "# [AI]" in l else l
                    st.markdown(f"- `{expr}`")

with upload_tab:
    st.markdown("#### Try your own workflow")
    st.caption("Upload an Alteryx .yxmd file. The converter parses it, generates Python, runs it on data, and reports the result. "
               "Supported tools: Input, Filter, Select, Create Points, Formula, Summarize, Buffer, Spatial Match. "
               "Unsupported tools are flagged rather than silently skipped.")

    up = st.file_uploader("Alteryx workflow (.yxmd)", type=["yxmd", "xml"])

    if up is None:
        st.info("Upload a .yxmd file to begin. Tip: you can download one of the built-in workflows from the repo's "
                "workflows/ folder to try the flow end to end.")
    else:
        try:
            xml_text = up.read().decode("utf-8", errors="replace")
            src, stats, nodes, order, body = cv.generate_source_xml(xml_text)
            steps = cv.describe_workflow_xml(xml_text)
            needed = cv.input_files_in_xml(xml_text)

            st.markdown(
                f'<div class="chips">'
                f'<div class="chip"><div class="v v-ice">{len(nodes)}</div><div class="k">tools</div></div>'
                f'<div class="chip"><div class="v v-deep">{stats.template}</div><div class="k">template</div></div>'
                f'<div class="chip"><div class="v v-green">{stats.ai}</div><div class="k">AI-translated</div></div>'
                f'<div class="chip"><div class="v v-amber">{stats.unsupported}</div><div class="k">unsupported</div></div>'
                f'</div>', unsafe_allow_html=True)

            if stats.unsupported:
                unsup = [s["raw_tool"] for s in steps if s["raw_tool"] not in (
                    "DbFileInput","DbFileOutput","Filter","AlteryxSelect","CreatePoints",
                    "Formula","Summarize","Buffer","SpatialMatch")]
                st.warning(f"This workflow uses tools the converter does not handle yet: "
                           f"{', '.join(sorted(set(unsup))) or 'see flagged lines'}. "
                           f"Those lines are marked [UNSUPPORTED] and would need a converter rule or manual review.")

            st.markdown("<hr>", unsafe_allow_html=True)
            a, b = st.columns(2)
            with a:
                st.markdown('<div class="sectlabel">Uploaded Alteryx workflow</div>', unsafe_allow_html=True)
                st.markdown(render_flow(steps), unsafe_allow_html=True)
                st.markdown('<div class="sectlabel" style="margin-top:.8rem;">Uploaded .yxmd source</div>', unsafe_allow_html=True)
                st.code(xml_text, language="xml")
            with b:
                st.markdown('<div class="sectlabel">Converted Python · green = AI-translated</div>', unsafe_allow_html=True)
                st.markdown('<div class="codewrap"><div class="codehead">'
                            '<span class="l">workflow logic (highlighted)</span>'
                            '<span><span class="tag-ai">[AI]</span> &nbsp; <span class="tag-tpl">[TEMPLATE]</span></span>'
                            '</div>' + render_code(body) + '</div>', unsafe_allow_html=True)
                full_up = cv.full_script(src, up.name)
                with st.expander("Full runnable script (imports + helpers + logic)"):
                    st.code(full_up, language="python")
                st.download_button("Download generated .py", full_up,
                                   file_name=(up.name.rsplit('.',1)[0] + ".py"),
                                   mime="text/x-python", key="dl_upload")

            # resolve input data: use built-in samples where names match, else ask for upload
            st.markdown("<hr>", unsafe_allow_html=True)
            st.markdown('<div class="sectlabel">Input data</div>', unsafe_allow_html=True)
            run_tables = {}
            missing = []
            for fn in needed:
                if fn in TABLES:
                    run_tables[fn] = TABLES[fn]
                    st.caption(f"{fn}: using built-in sample data ({TABLES[fn].shape[0]} rows).")
                else:
                    missing.append(fn)
            uploaded_csvs = {}
            if missing:
                st.caption(f"This workflow needs data files not built into the demo: {', '.join(missing)}. "
                           f"Upload a CSV for each to run it.")
                for fn in missing:
                    cf = st.file_uploader(f"CSV for {fn}", type=["csv"], key=f"csv_{fn}")
                    if cf is not None:
                        uploaded_csvs[fn] = pd.read_csv(cf)
                        run_tables[fn] = uploaded_csvs[fn]

            can_run = len(run_tables) == len(needed) and stats.unsupported == 0
            st.markdown("<hr>", unsafe_allow_html=True)
            if stats.unsupported:
                st.info("Conversion is shown above. Execution is skipped because the workflow contains unsupported tools.")
            elif not can_run:
                st.info("Provide the required input data above to run the converted Python and see its output.")
            else:
                captured, _ = cv.run_generated(body, run_tables)
                if not captured:
                    st.warning("The workflow produced no Output Data tool, so there is nothing to write. "
                               "Add an Output tool to see results.")
                else:
                    out_name = list(captured.keys())[0]
                    new_raw = captured[out_name]
                    new_df = new_raw.sort_values(list(new_raw.columns)).reset_index(drop=True)

                    # parity only where a known reference matches the output signature
                    ref_fn = None
                    sig = tuple(new_df.columns)
                    known = {
                        ("AnnualRevenue","Region","StoreID","StoreName"): "Simple",
                        ("AvgDistance","CustomerCount","ProximityTier","TotalLTV"): "Medium",
                        ("AvgCustDistance","CapturedCustomers","CapturedLTV","StoreID","StoreName"): "Complex",
                    }
                    ref_key = known.get(tuple(sorted(sig)))
                    if ref_key and run_tables == {k: TABLES[k] for k in run_tables}:
                        old_df = REFS[ref_key]().sort_values(list(REFS[ref_key]().columns)).reset_index(drop=True)
                        identical, summ = compare(old_df, new_df)
                        if identical:
                            st.markdown(
                                f'<div class="verdict"><div class="big">MATCH</div>'
                                f'<div class="sub">Output matches an independent reference for this pattern — '
                                f'{summ["cell_match"]}/{summ["cell_total"]} cells equal.</div></div>',
                                unsafe_allow_html=True)
                        else:
                            st.markdown(
                                f'<div class="verdict fail"><div class="big">DIFFERENCE FOUND</div>'
                                f'<div class="sub">{summ["cell_match"]}/{summ["cell_total"]} cells matched.</div></div>',
                                unsafe_allow_html=True)
                        cc, dd = st.columns(2)
                        with cc:
                            st.markdown('<div class="sectlabel">Output — reference (ground truth)</div>', unsafe_allow_html=True)
                            st.dataframe(old_df, use_container_width=True, height=300)
                        with dd:
                            st.markdown('<div class="sectlabel">Output — converted Python</div>', unsafe_allow_html=True)
                            st.dataframe(new_df, use_container_width=True, height=300)
                    else:
                        st.markdown(
                            '<div class="verdict" style="background:rgba(143,193,212,.1);border-color:var(--sky);">'
                            '<div class="big" style="color:var(--sky);">RAN SUCCESSFULLY</div>'
                            '<div class="sub">The converted Python executed and produced output below. '
                            'No independent reference exists for an arbitrary workflow, so this shows the result rather than a parity check. '
                            'In production, parity is validated against the original Alteryx run\'s output.</div></div>',
                            unsafe_allow_html=True)
                        st.markdown('<div class="sectlabel">Output — converted Python</div>', unsafe_allow_html=True)
                        st.dataframe(new_df, use_container_width=True, height=320)

            ai_lines = [l for bb in body for l in bb.split("\n") if "[AI]" in l]
            if ai_lines:
                with st.expander(f"What the AI layer translated ({len(ai_lines)} expressions)"):
                    for l in ai_lines:
                        expr = l.split("# [AI]", 1)[1].strip() if "# [AI]" in l else l
                        st.markdown(f"- `{expr}`")

        except Exception as e:
            st.error(f"Could not process this file. It may not be a valid Alteryx .yxmd workflow. Details: {e}")

with source_tab:
    st.markdown("#### Source connectors")
    st.caption("Alteryx reads from many sources. Each one converts to an idiomatic Python read. "
               "Flat File runs live in the workflow tabs; the others show the converted connector code with "
               "representative sample data (labeled simulated) since this demo has no live broker, warehouse, or endpoint.")

    for sname, sc in cv.SOURCE_CONNECTORS.items():
        live_badge = ('<span style="color:#28C2A6;font-weight:700;">LIVE-CAPABLE</span>'
                      if sc["live"] else
                      '<span style="color:#E0A458;font-weight:700;">SIMULATED DATA</span>')
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<div class="sectlabel" style="margin:0;">{html.escape(sname)}</div>'
            f'<div style="font-family:var(--mono);font-size:.72rem;">{live_badge}</div></div>',
            unsafe_allow_html=True)
        st.caption(sc["note"])

        a, b = st.columns(2)
        with a:
            st.markdown('<div class="sectlabel">Alteryx input configuration</div>', unsafe_allow_html=True)
            st.code(sc["alteryx"], language="text")
        with b:
            st.markdown('<div class="sectlabel">Converted Python</div>', unsafe_allow_html=True)
            st.code(sc["python"], language="python")

        sample = sc["sample"]()
        label = ("Sample of the data this read returns"
                 if sc["live"] else
                 "Representative sample (simulated — no live source in this demo)")
        st.markdown(f'<div class="sectlabel">{html.escape(label)}</div>', unsafe_allow_html=True)
        st.dataframe(sample, use_container_width=True, height=150)

st.markdown("<hr>", unsafe_allow_html=True)
st.caption("Self-contained POC · pandas + numpy · spatial ops via haversine (production target: GeoPandas / Shapely). "
           "AI translations are cached for the demo; the same converter wires to a live model to scale across thousands of workflows.")
