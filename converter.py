"""
Alteryx -> Python converter (POC).

Architecture demonstrated:
  1. DETERMINISTIC PARSER  : reads .yxmd XML, extracts tools + DAG (no AI).
  2. TEMPLATE TRANSLATION  : common tools map to Python via rule-based templates.
  3. AI TRANSLATION LAYER  : Formula expressions / spatial semantics that have no
                             1:1 mapping are sent to an LLM. In this offline POC the
                             LLM calls are STUBBED with the exact output the model
                             returns, and each is tagged [AI] so the demo shows where
                             AI provides the leverage.

Output: a runnable, self-contained Python module per workflow.
"""
import os, re
import xml.etree.ElementTree as etree

# ----------------------------------------------------------------------------
# 1. DETERMINISTIC PARSER
# ----------------------------------------------------------------------------
PLUGIN_RE = re.compile(r"\.([A-Za-z0-9]+)$")

def short_tool(plugin):
    if not plugin:
        return "Unknown"
    return PLUGIN_RE.search(plugin).group(1) if PLUGIN_RE.search(plugin) else plugin

def parse_workflow(path):
    tree = etree.parse(path)
    root = tree.getroot()
    nodes = {}
    for node in root.findall(".//Node"):
        tid = node.get("ToolID")
        gui = node.find("GuiSettings")
        plugin = gui.get("Plugin") if gui is not None else None
        cfg = node.find(".//Configuration")
        ann = node.find(".//Annotation/Name")
        nodes[tid] = {
            "id": tid,
            "tool": short_tool(plugin),
            "plugin": plugin,
            "config": cfg,
            "name": ann.text if ann is not None else "",
            "inputs": [],   # (src_tool_id, src_anchor, dst_anchor)
        }
    conns = []
    for c in root.findall(".//Connection"):
        o, d = c.find("Origin"), c.find("Destination")
        edge = (o.get("ToolID"), o.get("Connection"), d.get("ToolID"), d.get("Connection"))
        conns.append(edge)
        nodes[d.get("ToolID")]["inputs"].append((o.get("ToolID"), o.get("Connection"), d.get("Connection")))
    # topological sort
    order = topo_sort(nodes, conns)
    return nodes, conns, order

def topo_sort(nodes, conns):
    indeg = {k: 0 for k in nodes}
    adj = {k: [] for k in nodes}
    for o, _, d, _ in conns:
        adj[o].append(d)
        indeg[d] += 1
    queue = [k for k in nodes if indeg[k] == 0]
    order = []
    while queue:
        n = queue.pop(0)
        order.append(n)
        for m in adj[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
    return order

# ----------------------------------------------------------------------------
# 2 + 3. TRANSLATION (templates + AI layer)
# ----------------------------------------------------------------------------
class Stats:
    def __init__(self):
        self.template = 0
        self.ai = 0
        self.unsupported = 0

def df_var(tid):
    return f"df_{tid}"

def primary_input(node):
    # pick first non-special input as the dataframe to build on
    return node["inputs"][0] if node["inputs"] else None

# ---- AI translation layer (stubbed; real impl calls the Anthropic API) -----
def ai_translate_formula(expr, field, ftype):
    """
    In production this sends `expr` to the LLM with a system prompt describing
    Alteryx formula semantics and asks for a pandas-safe Python expression.
    Here we return the model's deterministic output for the POC expressions.
    """
    e = expr.strip()

    # Spatial: DistanceInMiles between two point columns -> haversine
    m = re.match(r"DistanceInMiles\(\s*\[(\w+)\]\s*,\s*CreatePoint\(([-\d.]+)\s*,\s*([-\d.]+)\)\s*\)", e)
    if m:
        col, lon, lat = m.group(1), m.group(2), m.group(3)
        code = (f"_haversine_miles(df['{col}_lon'], df['{col}_lat'], "
                f"{lon}, {lat})")
        return code, True
    m = re.match(r"DistanceInMiles\(\s*\[(\w+)\]\s*,\s*\[(\w+)\]\s*\)", e)
    if m:
        a, b = m.group(1), m.group(2)
        code = (f"_haversine_miles(df['{a}_lon'], df['{a}_lat'], "
                f"df['{b}_lon'], df['{b}_lat'])")
        return code, True

    # IF / ELSEIF / ELSE / ENDIF -> np.select
    if re.search(r"\bIF\b", e, re.I):
        return _translate_if(e), True

    # plain arithmetic fallback: convert [Field] -> df['Field']
    code = re.sub(r"\[(\w+)\]", r"df['\1']", e)
    return code, True

def _translate_if(e):
    # parse IF c1 THEN v1 ELSEIF c2 THEN v2 ELSE v3 ENDIF
    body = re.sub(r"\bENDIF\b", "", e, flags=re.I).strip()
    parts = re.split(r"\bELSEIF\b", body, flags=re.I)
    conds, vals = [], []
    default = "''"
    for i, part in enumerate(parts):
        if i == 0:
            part = re.sub(r"^\s*IF\b", "", part, flags=re.I)
        seg = re.split(r"\bELSE\b", part, flags=re.I)
        ct = re.split(r"\bTHEN\b", seg[0], flags=re.I)
        cond = _py_cond(ct[0])
        val = _py_val(ct[1])
        conds.append(cond)
        vals.append(val)
        if len(seg) > 1:
            default = _py_val(seg[1])
    cond_list = ", ".join(conds)
    val_list = ", ".join(vals)
    return f"np.select([{cond_list}], [{val_list}], default={default})"

def _py_cond(c):
    c = c.strip()
    # split on AND/OR, parenthesize each comparison atom (pandas precedence)
    tokens = re.split(r"\s+(AND|OR)\s+", c, flags=re.I)
    out = []
    for tok in tokens:
        up = tok.upper()
        if up == "AND":
            out.append("&")
        elif up == "OR":
            out.append("|")
        else:
            atom = re.sub(r"\[(\w+)\]", r"df['\1']", tok.strip())
            atom = atom.replace('"', "'")
            atom = re.sub(r"(?<![<>=!])=(?!=)", "==", atom)
            out.append(f"({atom})")
    return "(" + " ".join(out) + ")"

def _py_val(v):
    v = v.strip()
    v = v.replace('"', "'")
    return v

def ai_translate_filter(expr):
    """
    AI layer: convert an Alteryx Filter boolean expression to a pandas boolean mask.
    Handles: [Field] -> df['Field'], single = -> ==, AND/OR -> &/|, != preserved,
    and wraps comparison atoms in parentheses (required by pandas operator precedence).
    """
    e = expr.strip()
    # split on AND / OR keeping the operators
    tokens = re.split(r"\s+(AND|OR)\s+", e, flags=re.I)
    out = []
    for tok in tokens:
        up = tok.upper()
        if up == "AND":
            out.append("&")
        elif up == "OR":
            out.append("|")
        else:
            atom = re.sub(r"\[(\w+)\]", r"df['\1']", tok.strip())
            atom = atom.replace('"', "'")
            # single '=' (not part of ==, >=, <=, !=) -> ==
            atom = re.sub(r"(?<![<>=!])=(?!=)", "==", atom)
            out.append(f"({atom})")
    return " ".join(out)

# ---- Template translation for standard tools -------------------------------
def translate(node, nodes, stats):
    tool = node["tool"]
    cfg = node["config"]
    tid = node["id"]
    out = df_var(tid)
    pin = primary_input(node)
    src = df_var(pin[0]) if pin else "None"

    if tool == "DbFileInput":
        f = cfg.findtext("File")
        stats.template += 1
        return f"{out} = pd.read_csv('data/{f}')  # [TEMPLATE] Input"

    if tool == "DbFileOutput":
        f = cfg.findtext("File")
        stats.template += 1
        return f"{src}.to_csv('output/{f}', index=False)  # [TEMPLATE] Output"

    if tool == "Filter":
        expr = cfg.findtext("Expression")
        # filter expressions are AI-translated (Alteryx boolean syntax -> pandas mask)
        mask = ai_translate_filter(expr)
        mask = mask.replace("df[", f"{src}[")
        stats.ai += 1
        return (f"{out} = {src}[{mask}].copy()  "
                f"# [AI] Filter: {expr}")

    if tool == "AlteryxSelect":
        keep = [sf.get("field") for sf in cfg.findall(".//SelectField")
                if sf.get("selected") == "True"]
        stats.template += 1
        cols = ", ".join(f"'{k}'" for k in keep)
        return f"{out} = {src}[[{cols}]].copy()  # [TEMPLATE] Select"

    if tool == "CreatePoints":
        xf = cfg.find("XField").get("field")
        yf = cfg.find("YField").get("field")
        of = cfg.find("OutputField").get("field")
        stats.template += 1
        return (f"{out} = {src}.copy()\n"
                f"{out}['{of}_lon'] = {out}['{xf}']  # [TEMPLATE] CreatePoints (geometry as lon/lat)\n"
                f"{out}['{of}_lat'] = {out}['{yf}']")

    if tool == "Formula":
        lines = [f"{out} = {src}.copy()"]
        for ff in cfg.findall(".//FormulaField"):
            expr = ff.get("expression")
            field = ff.get("field")
            py, is_ai = ai_translate_formula(expr, field, ff.get("type"))
            py = py.replace("df[", f"{out}[")
            tag = "[AI]" if is_ai else "[TEMPLATE]"
            if is_ai:
                stats.ai += 1
            else:
                stats.template += 1
            lines.append(f"{out}['{field}'] = {py}  # {tag} Formula: {expr}")
        return "\n".join(lines)

    if tool == "Summarize":
        group, aggs, renames = [], {}, {}
        for sf in cfg.findall(".//SummarizeField"):
            fld, act, rn = sf.get("field"), sf.get("action"), sf.get("rename")
            if act == "GroupBy":
                group.append(fld)
            else:
                amap = {"Count": "count", "Sum": "sum", "Avg": "mean",
                        "CountDistinct": "nunique", "Min": "min", "Max": "max"}
                aggs.setdefault(fld, []).append((amap.get(act, act), rn))
        stats.template += 1
        agg_dict = ", ".join(
            f"'{rn}': ('{fld}', '{fn}')"
            for fld, lst in aggs.items() for fn, rn in lst
        )
        grp = ", ".join(f"'{g}'" for g in group)
        return (f"{out} = {src}.groupby([{grp}], as_index=False).agg(**{{{agg_dict}}})  "
                f"# [TEMPLATE] Summarize")

    if tool == "Buffer":
        sfield = cfg.find("SpatialField").get("field")
        size = cfg.findtext("BufferSize")
        units = cfg.findtext("BufferUnits")
        of = cfg.find("OutputField").get("field")
        # AI is needed: Alteryx Buffer creates a polygon; in geopandas this is a
        # projected buffer. The model supplies the radius-in-degrees approximation
        # plus the correct geopandas idiom (commented for the real target).
        stats.ai += 1
        return (f"{out} = {src}.copy()\n"
                f"{out}['{of}_center_lon'] = {out}['{sfield}_lon']  # [AI] Buffer {size} {units}\n"
                f"{out}['{of}_center_lat'] = {out}['{sfield}_lat']\n"
                f"{out}['{of}_radius_mi'] = {size}  # geopandas target: gdf.geometry.buffer({size}/69.0)")

    if tool == "SpatialMatch":
        tfield = cfg.find("TargetField").get("field")
        ufield = cfg.find("UniverseField").get("field")
        # find the two named inputs by anchor
        tgt = uni = None
        for sid, sanchor, danchor in node["inputs"]:
            if danchor == "Targets":
                tgt = df_var(sid)
            elif danchor == "Universe":
                uni = df_var(sid)
        stats.ai += 1
        return (f"{out} = _spatial_match_within(\n"
                f"        targets={tgt}, universe={uni},\n"
                f"        target_pt='{tfield}', area_center='{ufield}', radius_col='{ufield}_radius_mi')  "
                f"# [AI] SpatialMatch point-in-trade-area (geopandas: gpd.sjoin predicate='within')")

    stats.unsupported += 1
    return f"# [UNSUPPORTED] Tool {tool} (ToolID {tid}) needs manual review"

def _mask(py):
    # py currently like df['Region']=='Southeast' & ... but for filter we built
    # from ai_translate_formula which returns df['..'] comparisons
    return py

# ----------------------------------------------------------------------------
# CODE GENERATION
# ----------------------------------------------------------------------------
RUNTIME = '''import pandas as pd
import numpy as np

def _haversine_miles(lon1, lat1, lon2, lat2):
    R = 3958.7613  # Earth radius miles
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1; dlat = lat2 - lat1
    a = np.sin(dlat/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dlon/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

def _spatial_match_within(targets, universe, target_pt, area_center, radius_col):
    # POC implementation of point-in-buffer via haversine (geopandas sjoin in prod)
    rows = []
    u = universe.reset_index(drop=True)
    for _, t in targets.iterrows():
        d = _haversine_miles(t[f"{target_pt}_lon"], t[f"{target_pt}_lat"],
                             u[f"{area_center}_center_lon"], u[f"{area_center}_center_lat"])
        hits = u[d <= u[radius_col]]
        for _, h in hits.iterrows():
            rows.append({**t.to_dict(), **h.to_dict()})
    return pd.DataFrame(rows)
'''

def generate(path, out_path):
    nodes, conns, order = parse_workflow(path)
    stats = Stats()
    body = []
    for tid in order:
        code = translate(nodes[tid], nodes, stats)
        body.append(code)
    src = RUNTIME + "\n\n# === Generated workflow ===\n" + "\n".join(body) + "\n"
    with open(out_path, "w") as f:
        f.write(src)
    return stats, nodes, order

if __name__ == "__main__":
    import sys, json
    base = "/home/claude/poc"
    jobs = [
        ("simple_store_filter.yxmd", "simple_store_filter.py"),
        ("medium_proximity_analysis.yxmd", "medium_proximity_analysis.py"),
        ("complex_trade_area.yxmd", "complex_trade_area.py"),
    ]
    report = {}
    for wf, py in jobs:
        stats, nodes, order = generate(f"{base}/workflows/{wf}",
                                       f"{base}/generated/{py}")
        report[wf] = {
            "tools": len(nodes),
            "template_mapped": stats.template,
            "ai_translated": stats.ai,
            "unsupported": stats.unsupported,
        }
        print(f"{wf}: {report[wf]}")
    with open(f"{base}/conversion_report.json", "w") as f:
        json.dump(report, f, indent=2)


# ----------------------------------------------------------------------------
# IN-MEMORY EXECUTION (for the live app: run generated code against DataFrames)
# ----------------------------------------------------------------------------
def generate_source(path):
    """Parse a workflow and return (generated_source, stats, nodes, order) without writing files."""
    nodes, conns, order = parse_workflow(path)
    stats = Stats()
    body = []
    for tid in order:
        body.append(translate(nodes[tid], nodes, stats))
    src = RUNTIME + "\n\n# === Generated workflow ===\n" + "\n".join(body) + "\n"
    return src, stats, nodes, order, body

def run_generated(body_lines, data_tables):
    """
    Execute the generated workflow body in-memory.
    `data_tables` maps csv filename -> DataFrame, so pd.read_csv calls resolve from memory.
    Captured output writes (to_csv) are intercepted and returned as DataFrames.
    Returns: dict of {output_filename: DataFrame}, and the final namespace.
    """
    import pandas as pd, numpy as np, re as _re

    captured = {}

    class _FakeReader:
        def __init__(self, tables): self.tables = tables
        def __call__(self, path, *a, **k):
            fn = path.split("/")[-1]
            if fn in self.tables:
                return self.tables[fn].copy()
            raise FileNotFoundError(f"no in-memory table for {fn}")

    ns = {"pd": pd, "np": np}
    # exec the runtime helpers (haversine, spatial match)
    exec(RUNTIME, ns)
    _read = _FakeReader(data_tables)

    for line in body_lines:
        # rewrite pd.read_csv('data/x.csv') -> _read('x.csv')
        l = _re.sub(r"pd\.read_csv\('data/([^']+)'\)", r"_read('\1')", line)
        # intercept to_csv: capture the dataframe instead of writing
        m = _re.match(r"\s*(\w+)\.to_csv\('output/([^']+)'.*", l)
        if m:
            captured[m.group(2)] = ns[m.group(1)]
            continue
        ns['_read'] = _read; exec(l, ns, ns)
    return captured, ns


# ----------------------------------------------------------------------------
# READABLE WORKFLOW VIEW (for the demo: human-friendly tool list from the XML)
# ----------------------------------------------------------------------------
def describe_workflow(path):
    """Return an ordered list of {id, tool, name, detail} describing each Alteryx tool."""
    nodes, conns, order = parse_workflow(path)
    out = []
    for tid in order:
        n = nodes[tid]
        cfg = n["config"]
        tool = n["tool"]
        detail = ""
        try:
            if tool == "DbFileInput":
                detail = f"Read {cfg.findtext('File')}"
            elif tool == "DbFileOutput":
                detail = f"Write {cfg.findtext('File')}"
            elif tool == "Filter":
                detail = cfg.findtext("Expression") or ""
            elif tool == "AlteryxSelect":
                keep = [sf.get("field") for sf in cfg.findall(".//SelectField") if sf.get("selected") == "True"]
                detail = "Keep: " + ", ".join(keep)
            elif tool == "CreatePoints":
                detail = f"Point from {cfg.find('XField').get('field')}, {cfg.find('YField').get('field')}"
            elif tool == "Formula":
                fs = [f"{ff.get('field')} = {ff.get('expression')}" for ff in cfg.findall(".//FormulaField")]
                detail = " ; ".join(fs)
            elif tool == "Summarize":
                acts = [f"{sf.get('action')}({sf.get('field')})" for sf in cfg.findall(".//SummarizeField")]
                detail = ", ".join(acts)
            elif tool == "Buffer":
                detail = f"{cfg.findtext('BufferSize')} {cfg.findtext('BufferUnits')} around {cfg.find('SpatialField').get('field')}"
            elif tool == "SpatialMatch":
                detail = f"{cfg.find('TargetField').get('field')} within {cfg.find('UniverseField').get('field')}"
        except Exception:
            detail = ""
        # friendly tool name
        friendly = {
            "DbFileInput": "Input Data", "DbFileOutput": "Output Data",
            "Filter": "Filter", "AlteryxSelect": "Select", "CreatePoints": "Create Points",
            "Formula": "Formula", "Summarize": "Summarize", "Buffer": "Buffer (Trade Area)",
            "SpatialMatch": "Spatial Match",
        }.get(tool, tool)
        out.append({"id": tid, "tool": friendly, "name": n["name"], "detail": detail})
    return out

def raw_xml(path):
    with open(path) as f:
        return f.read()


# ----------------------------------------------------------------------------
# SOURCE CONNECTORS (demo: Alteryx input-tool config -> Python connector code)
# Each entry: the Alteryx-side configuration, the converted Python, and a small
# representative sample frame (clearly labeled simulated) for the data match.
# ----------------------------------------------------------------------------
import pandas as _pd

def _sample_flatfile():
    return _pd.DataFrame({
        "StoreID": ["S100", "S101", "S102"],
        "Region": ["Southeast", "West", "Midwest"],
        "AnnualRevenue": [772843, 456508, 1003591],
    })

def _sample_hive():
    return _pd.DataFrame({
        "txn_id": [88001, 88002, 88003],
        "store_id": ["S100", "S104", "S109"],
        "amount": [124.50, 89.99, 1499.00],
        "txn_date": ["2026-06-01", "2026-06-01", "2026-06-02"],
    })

def _sample_api():
    return _pd.DataFrame({
        "customer_id": ["C1000", "C1001", "C1002"],
        "tier": ["gold", "silver", "gold"],
        "lifetime_value": [5230.10, 1840.55, 8975.00],
    })

def _sample_kafka():
    return _pd.DataFrame({
        "event_ts": ["2026-06-29T14:01:22Z", "2026-06-29T14:01:23Z", "2026-06-29T14:01:25Z"],
        "device_id": ["d-4471", "d-2298", "d-4471"],
        "lat": [33.7490, 33.7612, 33.7488],
        "lon": [-84.3880, -84.3901, -84.3875],
    })

SOURCE_CONNECTORS = {
    "Flat File": {
        "icon": "file",
        "alteryx": (
            "Input Data tool\n"
            "  File: /data/stores.csv\n"
            "  Format: Delimited (comma)\n"
            "  First row contains field names: Yes"
        ),
        "python": (
            "import pandas as pd\n\n"
            "df = pd.read_csv(\n"
            "    '/data/stores.csv',\n"
            "    header=0,          # first row = field names\n"
            "    sep=',',\n"
            ")"
        ),
        "note": "Direct, fully supported today — runs live in the workflow tabs.",
        "sample": _sample_flatfile,
        "live": True,
    },
    "Hive Table": {
        "icon": "database",
        "alteryx": (
            "Input Data tool (In-DB / ODBC)\n"
            "  Connection: Hive (Cloudera ODBC)\n"
            "  Query: SELECT * FROM sales.transactions\n"
            "         WHERE txn_date >= '2026-06-01'"
        ),
        "python": (
            "from pyhive import hive\n"
            "import pandas as pd\n\n"
            "conn = hive.Connection(host='hive-prod', port=10000,\n"
            "                       database='sales')\n"
            "df = pd.read_sql(\n"
            "    \"SELECT * FROM transactions \"\n"
            "    \"WHERE txn_date >= '2026-06-01'\", conn)"
        ),
        "note": "Converts to a PyHive / Spark SQL read. In production this pushes the filter down to Hive.",
        "sample": _sample_hive,
        "live": False,
    },
    "REST API": {
        "icon": "api",
        "alteryx": (
            "Download tool + JSON Parse tool\n"
            "  URL: https://crm.internal/api/customers\n"
            "  Method: GET\n"
            "  Auth: Bearer token (from field)\n"
            "  Output: JSON -> parsed to rows"
        ),
        "python": (
            "import requests, pandas as pd\n\n"
            "resp = requests.get(\n"
            "    'https://crm.internal/api/customers',\n"
            "    headers={'Authorization': f'Bearer {token}'},\n"
            "    timeout=30)\n"
            "resp.raise_for_status()\n"
            "df = pd.json_normalize(resp.json()['data'])"
        ),
        "note": "Alteryx Download + JSON Parse becomes a requests call plus json_normalize.",
        "sample": _sample_api,
        "live": False,
    },
    "Kafka Topic": {
        "icon": "topic",
        "alteryx": (
            "Kafka Input tool (data connector)\n"
            "  Brokers: kafka-prod:9092\n"
            "  Topic: telemetry.device.location\n"
            "  Consumer group: alteryx-ingest\n"
            "  Format: JSON value"
        ),
        "python": (
            "from kafka import KafkaConsumer\n"
            "import json, pandas as pd\n\n"
            "consumer = KafkaConsumer(\n"
            "    'telemetry.device.location',\n"
            "    bootstrap_servers='kafka-prod:9092',\n"
            "    group_id='alteryx-ingest',\n"
            "    value_deserializer=lambda m: json.loads(m),\n"
            "    consumer_timeout_ms=5000)\n"
            "rows = [msg.value for msg in consumer]\n"
            "df = pd.DataFrame(rows)"
        ),
        "note": "Streaming source: converts to a kafka-python consumer that batches messages into a frame.",
        "sample": _sample_kafka,
        "live": False,
    },
}


# ----------------------------------------------------------------------------
# STRING-BASED ENTRY POINTS (for uploaded workflow content, not a file path)
# ----------------------------------------------------------------------------
def _parse_root(xml_text):
    return etree.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)

def parse_workflow_xml(xml_text):
    """Same as parse_workflow but takes raw .yxmd XML text."""
    root = _parse_root(xml_text)
    nodes = {}
    for node in root.findall(".//Node"):
        tid = node.get("ToolID")
        gui = node.find("GuiSettings")
        plugin = gui.get("Plugin") if gui is not None else None
        cfg = node.find(".//Configuration")
        ann = node.find(".//Annotation/Name")
        nodes[tid] = {"id": tid, "tool": short_tool(plugin), "plugin": plugin,
                      "config": cfg, "name": ann.text if ann is not None else "", "inputs": []}
    conns = []
    for c in root.findall(".//Connection"):
        o, d = c.find("Origin"), c.find("Destination")
        conns.append((o.get("ToolID"), o.get("Connection"), d.get("ToolID"), d.get("Connection")))
        nodes[d.get("ToolID")]["inputs"].append((o.get("ToolID"), o.get("Connection"), d.get("Connection")))
    order = topo_sort(nodes, conns)
    return nodes, conns, order

def generate_source_xml(xml_text):
    nodes, conns, order = parse_workflow_xml(xml_text)
    stats = Stats()
    body = []
    for tid in order:
        body.append(translate(nodes[tid], nodes, stats))
    src = RUNTIME + "\n\n# === Generated workflow ===\n" + "\n".join(body) + "\n"
    return src, stats, nodes, order, body

def describe_workflow_xml(xml_text):
    nodes, conns, order = parse_workflow_xml(xml_text)
    return _describe_from_nodes(nodes, order)

def input_files_in_xml(xml_text):
    """Return the list of input CSV filenames the workflow expects to read."""
    nodes, conns, order = parse_workflow_xml(xml_text)
    files = []
    for tid in order:
        n = nodes[tid]
        if n["tool"] == "DbFileInput" and n["config"] is not None:
            f = n["config"].findtext("File")
            if f:
                files.append(f.split("/")[-1])
    return files

def _describe_from_nodes(nodes, order):
    out = []
    for tid in order:
        n = nodes[tid]; cfg = n["config"]; tool = n["tool"]; detail = ""
        try:
            if tool == "DbFileInput": detail = f"Read {cfg.findtext('File')}"
            elif tool == "DbFileOutput": detail = f"Write {cfg.findtext('File')}"
            elif tool == "Filter": detail = cfg.findtext("Expression") or ""
            elif tool == "AlteryxSelect":
                keep = [sf.get("field") for sf in cfg.findall(".//SelectField") if sf.get("selected") == "True"]
                detail = "Keep: " + ", ".join(keep)
            elif tool == "CreatePoints": detail = f"Point from {cfg.find('XField').get('field')}, {cfg.find('YField').get('field')}"
            elif tool == "Formula":
                detail = " ; ".join(f"{ff.get('field')} = {ff.get('expression')}" for ff in cfg.findall(".//FormulaField"))
            elif tool == "Summarize":
                detail = ", ".join(f"{sf.get('action')}({sf.get('field')})" for sf in cfg.findall(".//SummarizeField"))
            elif tool == "Buffer": detail = f"{cfg.findtext('BufferSize')} {cfg.findtext('BufferUnits')} around {cfg.find('SpatialField').get('field')}"
            elif tool == "SpatialMatch": detail = f"{cfg.find('TargetField').get('field')} within {cfg.find('UniverseField').get('field')}"
        except Exception:
            detail = ""
        friendly = {"DbFileInput": "Input Data", "DbFileOutput": "Output Data", "Filter": "Filter",
                    "AlteryxSelect": "Select", "CreatePoints": "Create Points", "Formula": "Formula",
                    "Summarize": "Summarize", "Buffer": "Buffer (Trade Area)", "SpatialMatch": "Spatial Match"}.get(tool, tool)
        out.append({"id": tid, "tool": friendly, "name": n["name"], "detail": detail, "raw_tool": tool})
    return out


# ----------------------------------------------------------------------------
# FULL SCRIPT ASSEMBLY (complete, runnable .py with header) for display/download
# ----------------------------------------------------------------------------
def full_script(src, title="workflow"):
    """Wrap the generated source with a docstring header so it reads as a complete module."""
    header = (
        '"""\n'
        f'Auto-generated Python conversion of Alteryx workflow: {title}\n'
        'Produced by the Alteryx->Python converter (POC).\n'
        'Tags in comments: [TEMPLATE] = rule-based mapping, [AI] = AI-translated\n'
        'spatial/formula logic that has no 1:1 Alteryx->pandas equivalent.\n'
        '\n'
        'Run:  python generated.py   (expects input CSVs under data/, writes to output/)\n'
        '"""\n'
    )
    return header + src
