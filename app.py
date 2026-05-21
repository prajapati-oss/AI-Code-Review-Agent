
from __future__ import annotations

import json
import os
import time

import pandas as pd
import streamlit as st

from core.ast_parser       import parse_python_file
from core.clone_repo        import clone_repository
from core.confidence_engine import ConfidenceEngine
from core.llm_reviewer      import LLMReviewer, QuotaExhaustedError


st.set_page_config(
    page_title="AI Code Review Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Base ───────────────────────────────────────────── */
html,body,[class*="css"]{ font-family:'Inter',sans-serif; }
.stApp{ background:#080b11; color:#e2e8f0; }

/* ── Kill every white/grey area Streamlit injects ── */
html, body { background:#080b11 !important; }
[data-testid="stAppViewContainer"]{ background:#080b11 !important; }
[data-testid="stAppViewBlockContainer"]{ background:#080b11 !important; padding-top:1.5rem !important; }
[data-testid="stMain"]{ background:#080b11 !important; }
[data-testid="stMainBlockContainer"]{ background:#080b11 !important; }
.main .block-container{ background:#080b11 !important; padding-top:1.5rem !important; max-width:100% !important; }
header[data-testid="stHeader"]{ background:#080b11 !important; border-bottom:1px solid #191f2e !important; }
[data-testid="stDecoration"]{ display:none !important; }
[data-testid="stToolbar"]{ background:#080b11 !important; }
/* top orange bar Streamlit sometimes shows */
div[class*="StatusWidget"]{ display:none !important; }

[data-testid="stSidebar"]{ background:#0d0f18 !important; border-right:1px solid #191f2e; }
[data-testid="stSidebar"] *{ color:#cbd5e1 !important; }
[data-testid="stSidebar"] .stMarkdown h3{ color:#38bdf8 !important; font-size:.82rem; text-transform:uppercase; letter-spacing:.1em; }

/* ── Hero ───────────────────────────────────────────── */
.hero{
  background:linear-gradient(135deg,#0d1117 0%,#111827 100%);
  border:1px solid #1e2a3a; border-radius:18px;
  padding:2.6rem 2.4rem 2.2rem; margin-bottom:1.8rem;
  position:relative; overflow:hidden;
}
.hero::before{
  content:''; position:absolute; top:-100px; right:-100px;
  width:300px; height:300px;
  background:radial-gradient(circle,rgba(56,189,248,.09) 0%,transparent 65%);
  border-radius:50%;
}
.hero::after{
  content:''; position:absolute; bottom:-60px; left:40%;
  width:200px; height:200px;
  background:radial-gradient(circle,rgba(129,140,248,.06) 0%,transparent 65%);
  border-radius:50%;
}
.hero-badge{
  display:inline-block; background:#0f2335; border:1px solid #1e3a5f;
  color:#38bdf8; font-family:'JetBrains Mono',monospace;
  font-size:.68rem; font-weight:600; letter-spacing:.1em;
  text-transform:uppercase; padding:3px 10px; border-radius:999px;
  margin-bottom:.9rem;
}
.hero-title{
  font-family:'JetBrains Mono',monospace; font-size:2rem; font-weight:700;
  color:#f1f5f9; letter-spacing:-.5px; margin:0 0 .4rem; line-height:1.15;
}
.hero-title span{ color:#38bdf8; }
.hero-sub{
  font-family:'JetBrains Mono',monospace; font-size:.8rem; color:#475569; margin:0;
}
.dot{
  display:inline-block; width:7px; height:7px; border-radius:50%;
  background:#22c55e; margin-right:7px; vertical-align:middle;
  animation:pulse 2s infinite;
}
@keyframes pulse{
  0%,100%{ box-shadow:0 0 0 0 rgba(34,197,94,.5); }
  50%{ box-shadow:0 0 0 6px rgba(34,197,94,0); }
}
.hero-pills{ display:flex; gap:.6rem; flex-wrap:wrap; margin-top:1rem; }
.pill{
  background:#0f172a; border:1px solid #1e293b; border-radius:999px;
  color:#94a3b8; font-size:.7rem; padding:3px 10px;
  font-family:'JetBrains Mono',monospace;
}

/* ── Section label ──────────────────────────────────── */
.slabel{
  font-family:'JetBrains Mono',monospace; font-size:.7rem;
  text-transform:uppercase; letter-spacing:.13em; color:#334155;
  border-bottom:1px solid #191f2e; padding-bottom:.45rem;
  margin:1.8rem 0 1rem;
}

/* ── Metric card ────────────────────────────────────── */
.mcard{
  background:#0d0f18; border:1px solid #191f2e; border-radius:12px;
  padding:1.15rem 1.1rem; text-align:center;
  transition:border-color .2s, transform .2s;
}
.mcard:hover{ border-color:#38bdf8; transform:translateY(-2px); }
.mval{
  font-family:'JetBrains Mono',monospace; font-size:2.1rem;
  font-weight:700; line-height:1; margin-bottom:.3rem;
}
.mlbl{ font-size:.65rem; text-transform:uppercase; letter-spacing:.09em; color:#475569; }

/* ── Issue card ─────────────────────────────────────── */
.icard{
  background:#0d0f18; border:1px solid #191f2e;
  border-left:4px solid #334155; border-radius:10px;
  padding:1.05rem 1.2rem; margin-bottom:.7rem;
  transition:transform .15s, box-shadow .15s;
}
.icard:hover{ transform:translateX(5px); box-shadow:-5px 0 20px rgba(56,189,248,.06); }
.icard.critical{ border-left-color:#ef4444; }
.icard.high    { border-left-color:#f97316; }
.icard.medium  { border-left-color:#eab308; }
.icard.low     { border-left-color:#22c55e; }

.ititle{
  font-family:'JetBrains Mono',monospace; font-size:.88rem;
  font-weight:600; color:#f1f5f9; margin-bottom:.45rem;
}
.imeta{ display:flex; flex-wrap:wrap; gap:.4rem; margin-bottom:.6rem; }
.badge{
  display:inline-block; padding:2px 8px; border-radius:999px;
  font-size:.64rem; font-family:'JetBrains Mono',monospace;
  font-weight:600; text-transform:uppercase; letter-spacing:.06em;
}
.b-critical{ background:#450a0a; color:#fca5a5; }
.b-high    { background:#431407; color:#fdba74; }
.b-medium  { background:#422006; color:#fde047; }
.b-low     { background:#052e16; color:#86efac; }
.b-cat     { background:#0f172a; color:#7dd3fc; border:1px solid #1e3a5f; }
.b-hconf   { background:#052e16; color:#86efac; }
.b-mconf   { background:#3b2206; color:#fde047; }
.b-lconf   { background:#450a0a; color:#fca5a5; }

.idesc{ font-size:.81rem; color:#94a3b8; line-height:1.65; margin-bottom:.55rem; }
.ifix{
  background:#060810; border:1px solid #1e293b; border-radius:6px;
  padding:.55rem .85rem; font-family:'JetBrains Mono',monospace;
  font-size:.75rem; color:#67e8f9; line-height:1.6; white-space:pre-wrap;
}
.iloc{
  font-family:'JetBrains Mono',monospace; font-size:.66rem;
  color:#334155; margin-top:.45rem;
}

/* ── Verify banner ──────────────────────────────────── */
.vbanner{
  background:linear-gradient(90deg,#1c0a0a,#1a0f06);
  border:1px solid #7f1d1d; border-radius:10px;
  padding:.9rem 1.1rem; margin-bottom:1.1rem;
}
.vtitle{ font-family:'JetBrains Mono',monospace; font-size:.78rem; color:#fca5a5; font-weight:700; }
.vsub  { font-size:.74rem; color:#7f3737; margin-top:.25rem; line-height:1.5; }

/* ── Empty state ─────────────────────────────────────  */
.estate{ text-align:center; padding:5rem 1rem; }
.estate-icon{ font-size:3rem; margin-bottom:.9rem; }
.estate p{ font-size:.9rem; color:#475569; line-height:1.7; }

/* ── Streamlit overrides ────────────────────────────── */
.stButton>button{
  background:linear-gradient(135deg,#0ea5e9,#2563eb) !important;
  color:white !important; border:none !important; border-radius:9px !important;
  font-family:'Inter',sans-serif !important; font-weight:600 !important;
  font-size:.85rem !important; padding:.55rem 1.3rem !important;
  transition:opacity .2s, transform .1s !important;
}
.stButton>button:hover{ opacity:.88 !important; transform:translateY(-2px) !important; }
div[data-testid="stTextInput"] input{
  background:#060810 !important; border:1px solid #191f2e !important;
  color:#e2e8f0 !important; border-radius:8px !important;
  font-family:'JetBrains Mono',monospace !important; font-size:.84rem !important;
}
.stSelectbox>div>div{
  background:#060810 !important; border:1px solid #191f2e !important;
  border-radius:8px !important;
}
.stProgress>div>div>div>div{
  background:linear-gradient(90deg,#38bdf8,#818cf8) !important;
}
div[data-testid="stNumberInput"] input{
  background:#060810 !important; border:1px solid #191f2e !important;
  color:#e2e8f0 !important; border-radius:8px !important;
}
[data-testid="stExpander"]{
  background:#0d0f18 !important; border:1px solid #191f2e !important;
  border-radius:10px !important;
}
.stAlert{ border-radius:10px !important; }
#MainMenu,footer,[data-testid="stToolbar"]{ visibility:hidden; }
</style>
""", unsafe_allow_html=True)

IGNORE_DIRS = {
    "venv","env","myenv",".git","__pycache__","node_modules",
    "site-packages","dist","build",".idea",".vscode",
    ".tox",".eggs",".pytest_cache","htmlcov",
}
SEVERITY_ORDER = {"critical":0,"high":1,"medium":2,"low":3}

def collect_python_files(repo_path: str, limit: int = 50) -> list[str]:
    """Walk repo and collect .py files, skipping build/env directories."""
    files: list[str] = []
    for root, dirs, names in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for name in names:
            if name.endswith(".py"):
                files.append(os.path.join(root, name))
    return sorted(files)[:limit]


def conf_cls(label: str) -> str:
    """Return CSS class suffix for a confidence label."""
    return {"High Confidence":"hconf","Medium Confidence":"mconf"}.get(label,"lconf")


def render_issue_card(issue: dict) -> None:
    """Render a single review issue as a styled HTML card."""
    sev   = issue.get("severity","low").lower()
    label = issue.get("confidence_label","VERIFY THIS REVIEW")
    conf  = issue.get("confidence_score",0)
    cat   = issue.get("category","")
    fix   = issue.get("suggested_fix","").replace("<","&lt;").replace(">","&gt;")
    desc  = issue.get("description","").replace("<","&lt;").replace(">","&gt;")
    title = issue.get("title","").replace("<","&lt;").replace(">","&gt;")
    emoji = issue.get("severity_emoji","")
    fname = os.path.basename(issue.get("file",""))
    fn    = issue.get("function","")
    line  = issue.get("line_number",0)
    cb    = conf_cls(label)
    st.markdown(f"""
<div class="icard {sev}">
  <div class="ititle">{emoji} {title}</div>
  <div class="imeta">
    <span class="badge b-{sev}">{sev}</span>
    <span class="badge b-cat">{cat}</span>
    <span class="badge b-{cb}">&#x26A1; {conf}% &middot; {label}</span>
  </div>
  <div class="idesc">{desc}</div>
  <div class="ifix">&#x1F4A1; {fix}</div>
  <div class="iloc">&#x1F4C1; {fname} &nbsp;&middot;&nbsp; &fnof; {fn} &nbsp;&middot;&nbsp; line {line}</div>
</div>""", unsafe_allow_html=True)


def metric_card(col, value, label: str, color: str = "#38bdf8") -> None:
    col.markdown(f"""
<div class="mcard">
  <div class="mval" style="color:{color}">{value}</div>
  <div class="mlbl">{label}</div>
</div>""", unsafe_allow_html=True)

_defaults = {"reviews":[], "scan_done":False, "stats":{}, "repo_name":""}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

st.markdown("""
<div class="hero">
  <div class="hero-badge">&#x2B21; Agentic AI</div>
  <div class="hero-title">AI Code Review <span>Agent</span></div>
  <p class="hero-sub">
    <span class="dot"></span>
    Autonomous &nbsp;&middot;&nbsp; AST-Powered &nbsp;&middot;&nbsp;
    LLM-Reviewed &nbsp;&middot;&nbsp; Confidence-Scored
  </p>
  <div class="hero-pills">
    <span class="pill">GitPython</span>
    <span class="pill">Python AST</span>
    <span class="pill">Gemini 2.5 Flash</span>
    <span class="pill">Pydantic v2</span>
    <span class="pill">Streamlit</span>
  </div>
</div>
""", unsafe_allow_html=True)


with st.sidebar:
    st.markdown("### &#x1F517; Enter Repository URL")
    repo_url = st.text_input(
        "GitHub URL",
        placeholder="https://github.com/user/repo",
        label_visibility="collapsed",
    )

    
    c2 ,= st.columns(1)
    with c2:
        file_limit = st.number_input(
            "File limit", min_value=1, max_value=200, value=20,
            help="Max Python files to scan.\nFree Gemini tier: keep ≤ 5 to stay within 20 req/day"
        )
    c1, = st.columns(1)
    with c1:
        force_clone = st.checkbox("Re-clone", value=False,
                                   help="Force fresh clone even if already cached locally")

    run_btn = st.button("&#x1F680; Analyze Repository", use_container_width=True)

    # API key status
    api_key_ok = bool(st.secrets["GEMINI_API_KEY"].strip())
    if api_key_ok:
        st.success(" ", icon=None)
    else:
        st.error(
            "**GEMINI_API_KEY not set**\n\n"
            "Create a `.toml` file:\n```\nGEMINI_API_KEY=your_key_here\n```\n"
            "Get a free key at [aistudio.google.com](https://aistudio.google.com/app/apikey)"
        )

    st.divider()

    if st.session_state.scan_done and st.session_state.reviews:
        st.markdown("### &#x1F3DB; Filters")
        sev_f  = st.selectbox("Severity",   ["All","critical","high","medium","low"])
        cat_f  = st.selectbox("Category",
                               ["All","bug","security","performance",
                                "readability","maintainability"])
        conf_f = st.selectbox("Confidence",
                               ["All","High Confidence","Medium Confidence",
                                "VERIFY THIS REVIEW"])
        sort_f = st.selectbox("Sort by",
                               ["Severity ↑","Confidence ↓","File A→Z"])

        st.divider()
        st.markdown("### &#x2B07; Export Results")
        df_all = pd.DataFrame(st.session_state.reviews)
        rname  = st.session_state.repo_name
        st.download_button(
            "&#x1F4C4; Download CSV",
            data=df_all.to_csv(index=False).encode(),
            file_name=f"review_{rname}.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.download_button(
            "&#x1F4CB; Download JSON",
            data=json.dumps(st.session_state.reviews, indent=2).encode(),
            file_name=f"review_{rname}.json",
            mime="application/json",
            use_container_width=True,
        )
    else:
        sev_f = cat_f = conf_f = "All"
        sort_f = "Severity ↑"

    st.divider()
    #st.caption("CipherSchools Assignment · Gemini 2.5 Flash · Python AST · v1.0")

if run_btn:
    if not repo_url.strip():
        st.error("Please enter a GitHub repository URL in the sidebar.")
        st.stop()
    if not api_key_ok:
        st.error(
            "GEMINI_API_KEY is not set. "
            "Add it to your `.env` file and restart the app."
        )
        st.stop()

  
    st.session_state.reviews   = []
    st.session_state.scan_done = False
    st.session_state.stats     = {}

    # STEP 1  Clone
    with st.status("&#x1F4E6; Cloning repository...", expanded=True) as clone_status:
        t0     = time.time()
        result = clone_repository(repo_url.strip(), force_reclone=force_clone)
        secs   = round(time.time() - t0, 1)

        if not result["success"]:
            clone_status.update(label="Clone failed", state="error")
            st.error(f"**Git error:** {result['message']}")
            st.stop()

        repo_path = result["path"]
        repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git","")
        st.session_state.repo_name = repo_name
        clone_status.update(
            label=f"Cloned `{repo_name}` in {secs}s  &#x2192;  `{repo_path}`",
            state="complete",
        )

    # STEP 2  Discover files 
    py_files = collect_python_files(repo_path, limit=int(file_limit))
    if not py_files:
        st.warning("No Python `.py` files found in this repository.")
        st.stop()

    col_info1, col_info2 = st.columns(2)
    col_info1.info(f"&#x1F4C2; Found **{len(py_files)}** Python file(s) to analyse")
    col_info2.info(f"&#x23F3; Estimated time: **{len(py_files) * 3}–{len(py_files) * 6}s** depending on function count")

    # STEP 3  Init LLM reviewer 
    try:
        reviewer = LLMReviewer()
    except ValueError as e:
        st.error(str(e))
        st.stop()

    # STEP 4  Parse + Review loop 
    all_reviews : list[dict] = []
    errors      : list[str]  = []
    total_fns   : int        = 0
    quota_hit   : bool       = False

    progress_bar = st.progress(0, text="Starting analysis...")
    status_box   = st.empty()

    for idx, fp in enumerate(py_files):
        if quota_hit:
            break

        rel = os.path.relpath(fp, repo_path)
        progress_bar.progress(
            (idx + 1) / len(py_files),
            text=f"[{idx+1}/{len(py_files)}] Parsing `{rel}`",
        )

        # Parse
        try:
            parsed = parse_python_file(fp)
        except Exception as exc:
            errors.append(f"{rel} — parse exception: {exc}")
            continue

        if "error" in parsed:
            errors.append(f"{rel} — {parsed['error']}")
            continue

        fns = parsed.get("functions", [])
        total_fns += len(fns)

        # Review each function
        for fn in fns:
            status_box.caption(f"&#x1F916; Reviewing `{fn['name']}` in `{rel}`...")
            try:
                review = reviewer.review_code(
                    function_name=fn["name"],
                    source_code=fn["code"],
                    file_path=rel,
                )
            except QuotaExhaustedError:
                quota_hit = True
                st.error(
                    "**&#x1F6AB; Gemini Daily Quota Exhausted**\n\n"
                    "The Gemini free tier allows **20 API requests/day** per project.\n"
                    "Results below reflect functions reviewed **before** the limit was reached.\n\n"
                    "**How to fix:**\n"
                    "- &#x1F4B3; [Upgrade at aistudio.google.com](https://aistudio.google.com/plan_information)\n"
                    "- &#x23F0; Wait until **midnight UTC** (free quota resets daily)\n"
                    "- &#x1F511; Use a different GCP project (each gets its own 20 req/day)\n"
                    "- &#x2699;&#xFE0F; Reduce **File limit** in sidebar to ≤ 5"
                )
                break

            if review["success"]:
                processed = ConfidenceEngine.process_reviews(review["data"])
                for issue in processed["issues"]:
                    issue["file"]     = rel
                    issue["function"] = fn["name"]
                    all_reviews.append(issue)
            else:
                errors.append(f"{rel}::{fn['name']} — {review['error']}")

    progress_bar.empty()
    status_box.empty()

    if quota_hit and not all_reviews:
        st.stop()

    # ── Aggregate stats ───────────────────────────────────────────────────
    sev_counts = {"critical":0,"high":0,"medium":0,"low":0}
    for r in all_reviews:
        sev_counts[r.get("severity","low")] += 1

    risk = sum(
        ConfidenceEngine.SEVERITY_WEIGHT.get(r.get("severity","low"), 0)
        for r in all_reviews
    )
    avg_conf = (
        round(sum(r.get("confidence_score",0) for r in all_reviews) / len(all_reviews), 1)
        if all_reviews else 0.0
    )
    verify_count = sum(1 for r in all_reviews if r.get("confidence_label") == "VERIFY THIS REVIEW")

    st.session_state.reviews   = all_reviews
    st.session_state.scan_done = True
    st.session_state.stats     = {
        "files":        len(py_files),
        "functions":    total_fns,
        "total":        len(all_reviews),
        "sev":          sev_counts,
        "risk":         risk,
        "avg_conf":     avg_conf,
        "verify_count": verify_count,
        "errors":       errors,
    }

    if all_reviews:
        st.success(f"&#x2705; Scan complete — **{len(all_reviews)} issue(s)** found across **{total_fns}** function(s)")
    else:
        st.info("Scan complete. No issues found (or all functions had empty reviews).")

if st.session_state.scan_done:
    stats   = st.session_state.stats
    reviews = st.session_state.reviews

    # ── Overview metrics 
    st.markdown('<div class="slabel">&#x1F4CA; Overview</div>', unsafe_allow_html=True)
    oc1,oc2,oc3,oc4,oc5,oc6 = st.columns(6)
    metric_card(oc1, stats["files"],          "Files Scanned")
    metric_card(oc2, stats["functions"],      "Functions")
    metric_card(oc3, stats["total"],          "Issues Found",   "#f97316")
    metric_card(oc4, f'{stats["avg_conf"]}%', "Avg Confidence", "#a78bfa")
    rc = "#ef4444" if stats["risk"]>50 else "#f97316" if stats["risk"]>20 else "#22c55e"
    metric_card(oc5, stats["risk"],           "Risk Score",     rc)
    metric_card(oc6, stats["verify_count"],   "Verify Count",   "#ef4444")

    # ── Severity breakdown 
    st.markdown('<div class="slabel">&#x1F3AF; Severity Breakdown</div>', unsafe_allow_html=True)
    sc1,sc2,sc3,sc4 = st.columns(4)
    metric_card(sc1, stats["sev"]["critical"], "&#x1F534; Critical", "#ef4444")
    metric_card(sc2, stats["sev"]["high"],     "&#x1F7E0; High",     "#f97316")
    metric_card(sc3, stats["sev"]["medium"],   "&#x1F7E1; Medium",   "#eab308")
    metric_card(sc4, stats["sev"]["low"],      "&#x1F7E2; Low",      "#22c55e")

    # ── Charts
    if reviews:
        df = pd.DataFrame(reviews)
        st.markdown('<div class="slabel">&#x1F4C8; Distribution Charts</div>', unsafe_allow_html=True)
        ch1, ch2, ch3 = st.columns(3)

        with ch1:
            st.caption("Issues by Severity")
            sd = (
                df["severity"]
                .value_counts()
                .reindex(["critical","high","medium","low"], fill_value=0)
                .reset_index()
            )
            sd.columns = ["Severity","Count"]
            st.bar_chart(sd.set_index("Severity"), color="#38bdf8", height=190)

        with ch2:
            st.caption("Issues by Category")
            cd = df["category"].value_counts().reset_index()
            cd.columns = ["Category","Count"]
            st.bar_chart(cd.set_index("Category"), color="#818cf8", height=190)

        with ch3:
            st.caption("Issues by Confidence Tier")
            cmap = {
                "High Confidence":"High &#x2265;80%",
                "Medium Confidence":"Medium 50–79%",
                "VERIFY THIS REVIEW":"Low <50%",
            }
            cfd = df["confidence_label"].map(cmap).value_counts().reset_index()
            cfd.columns = ["Confidence","Count"]
            st.bar_chart(cfd.set_index("Confidence"), color="#f472b6", height=190)

    
    verify_issues = [r for r in reviews if r.get("confidence_label")=="VERIFY THIS REVIEW"]
    if verify_issues:
        st.markdown(
            '<div class="slabel">&#x26A0;&#xFE0F; Low-Confidence — Verify These Manually</div>',
            unsafe_allow_html=True,
        )
        st.markdown("""
<div class="vbanner">
  <div class="vtitle">&#x1F50D; VERIFY THIS REVIEW &mdash; Epistemic Humility Flag</div>
  <div class="vsub">
    These comments have a <strong>confidence score below 50%</strong>.
    The agent detected a potential issue but cannot determine this with high certainty.
    Treat as hints, not findings &mdash; manual code review is recommended before acting.
  </div>
</div>""", unsafe_allow_html=True)

        for issue in sorted(verify_issues, key=lambda r: r.get("confidence_score",0)):
            render_issue_card(issue)

    # ── Processing errors ─────────────────────────────────────────────────
    if stats.get("errors"):
        with st.expander(f"&#x26A0;&#xFE0F;  {len(stats['errors'])} file(s) had processing errors",
                         expanded=False):
            for e in stats["errors"]:
                st.caption(f"• {e}")

    # ── Main filtered list 
    filtered = list(reviews)
    if sev_f  != "All": filtered = [r for r in filtered if r.get("severity")        == sev_f]
    if cat_f  != "All": filtered = [r for r in filtered if r.get("category")         == cat_f]
    if conf_f != "All": filtered = [r for r in filtered if r.get("confidence_label") == conf_f]

    if   sort_f == "Severity ↑":    filtered.sort(key=lambda r: SEVERITY_ORDER.get(r.get("severity","low"),9))
    elif sort_f == "Confidence ↓":  filtered.sort(key=lambda r: r.get("confidence_score",0), reverse=True)
    else:                           filtered.sort(key=lambda r: r.get("file",""))

    st.markdown(
        f'<div class="slabel">&#x1F50E; All Issues '
        f'<span style="color:#38bdf8;font-size:.9em;">({len(filtered)} shown'
        f'{" of "+str(len(reviews)) if len(filtered)!=len(reviews) else ""})</span></div>',
        unsafe_allow_html=True,
    )

    if not filtered:
        st.markdown("""
<div class="estate">
  <div class="estate-icon">&#x2705;</div>
  <p>No issues match the current filters.<br>Try adjusting the sidebar filters.</p>
</div>""", unsafe_allow_html=True)
    else:
        for issue in filtered:
            render_issue_card(issue)

# Welcome / idle state 
elif not run_btn:
    st.markdown("""
<div class="estate">
  <div class="estate-icon">&#x1F50D;</div>
  <p>
    Paste a public GitHub repository URL into the sidebar<br>
    and click <strong style="color:#38bdf8;">Analyze Repository</strong> to begin.<br><br>
    <span style="font-size:.78rem;color:#334155;">
      Python repos &middot; AST function extraction &middot;
      Gemini 2.5 Flash review &middot; Confidence scoring &middot;
      CSV / JSON export
    </span>
  </p>
</div>""", unsafe_allow_html=True)
