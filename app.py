"""
app.py - Kuku Promo Finder: Internal Editorial Cue Sheet
A clean, production-focused tool for microdrama promo discovery and review.
"""

import os
import json
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from parser import parse_episode
from scorer import build_windows, score_windows, seconds_to_ts

load_dotenv()

st.set_page_config(
    page_title="Kuku Promo Finder",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

RAW_OUTPUTS = Path("raw_outputs")
SHOW_TITLE = "I Married a Broken Soldier. He was a Duke"

# ── Clean Editorial Theme (Linear / Frame.io Style) ──────────────────────────
st.markdown("""
<style>
/* Base typography */
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

/* =========================================================================
   Kuku TV Cinema Dark Theme (Default)
   ========================================================================= */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
    background-color: #080808 !important;
    color: #ffffff !important;
}

section[data-testid="stSidebar"] {
    background-color: #0d0d0d !important;
    border-right: 1px solid #1c1c1c !important;
}
section[data-testid="stSidebar"] > div {
    background-color: #0d0d0d !important;
}
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label {
    color: #f5f5f5 !important;
}

/* Sidebar Inputs & Controls */
section[data-testid="stSidebar"] .stSelectbox > div > div,
section[data-testid="stSidebar"] .stTextInput > div > div {
    background-color: #141414 !important;
    border: 1px solid #282828 !important;
    color: #ffffff !important;
}
section[data-testid="stSidebar"] .stButton > button {
    background-color: #ea1d24 !important;
    border: none !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    border-radius: 6px !important;
    transition: all 0.15s ease !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background-color: #ff2b32 !important;
    color: #ffffff !important;
}

/* Slider Accent */
.stSlider [data-baseweb="slider"] div[role="slider"] {
    background-color: #ea1d24 !important;
    border-color: #b91c1c !important;
}

/* Clean Unified Tabs (Kuku Red active line) */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px !important;
    border-bottom: 1px solid #222222 !important;
    background-color: transparent !important;
}
.stTabs [data-baseweb="tab"] {
    background-color: transparent !important;
    border: none !important;
    color: #888888 !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    padding: 8px 14px !important;
}
.stTabs [aria-selected="true"] {
    color: #ffffff !important;
    border-bottom: 2px solid #ea1d24 !important;
}

/* Next / React style Notification Toast */
div[data-testid="stToast"] {
    background-color: #141414 !important;
    border: 1px solid #262626 !important;
    border-left: 4px solid #ea1d24 !important;
    color: #ffffff !important;
    border-radius: 8px !important;
    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.6) !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    padding: 10px 16px !important;
}
div[data-testid="stToast"] [data-testid="stMarkdownContainer"] p {
    color: #ffffff !important;
    font-size: 13px !important;
    font-weight: 600 !important;
}

/* Container max width for clean editorial layout */
.block-container {
    max-width: 1040px !important;
    padding-top: 2rem !important;
    padding-bottom: 3rem !important;
    margin: 0 auto !important;
}

/* Clip Cue Card */
.cue-card {
    background: #121212;
    border: 1px solid #222222;
    border-radius: 10px;
    padding: 20px 22px;
    margin-bottom: 22px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.6);
    transition: border-color 0.2s ease;
}
.cue-card:hover {
    border-color: #383838;
}

/* Header tags */
.rank-tag {
    background: #ea1d24;
    color: #ffffff;
    border: none;
    font-size: 12px;
    font-weight: 800;
    padding: 4px 10px;
    border-radius: 6px;
    letter-spacing: 0.5px;
}
.ep-tag {
    font-size: 18px;
    font-weight: 800;
    color: #ffffff;
    margin-left: 8px;
}

/* High Contrast Upper Timeline Badge */
.time-tag {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    background: #1c1c1c;
    border: 1px solid #333333;
    padding: 4px 12px;
    border-radius: 6px;
    display: inline-flex;
    align-items: center;
    font-size: 13px;
    color: #ffffff;
}

/* Beat Blocks */
.beat-block {
    background: #181818;
    border: 1px solid #262626;
    border-radius: 8px;
    padding: 14px 16px;
    margin-top: 12px;
}
.beat-label {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #a0a0a0;
    margin-bottom: 4px;
}
.beat-text {
    font-size: 13.5px;
    color: #f5f5f5;
    line-height: 1.55;
}

/* =========================================================================
   Light Theme Support (Crisp, High-Contrast, Never Dull!)
   ========================================================================= */
[data-theme="light"] .stApp,
.stApp[data-theme="light"],
[data-theme="light"] [data-testid="stAppViewContainer"],
[data-theme="light"] [data-testid="stHeader"] {
    background-color: #f8fafc !important;
    color: #0f172a !important;
}
[data-theme="light"] section[data-testid="stSidebar"] {
    background-color: #ffffff !important;
    border-right: 1px solid #e2e8f0 !important;
}
[data-theme="light"] section[data-testid="stSidebar"] > div {
    background-color: #ffffff !important;
}
[data-theme="light"] section[data-testid="stSidebar"] * {
    color: #0f172a !important;
}
[data-theme="light"] .cue-card {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06) !important;
}
[data-theme="light"] .ep-tag {
    color: #0f172a !important;
}
[data-theme="light"] .beat-block {
    background: #f8fafc !important;
    border: 1px solid #e2e8f0 !important;
}
[data-theme="light"] .beat-text {
    color: #1e293b !important;
}
[data-theme="light"] .time-tag {
    background: #f1f5f9 !important;
    border: 1px solid #cbd5e1 !important;
    color: #0f172a !important;
}
</style>
""", unsafe_allow_html=True)


# ── Data Loading ─────────────────────────────────────────────────────────────

def load_promos():
    path = RAW_OUTPUTS / "promos.json"
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f).get("promos", [])
        except Exception:
            return []
    return []


# ── Rendering Helpers ────────────────────────────────────────────────────────

def get_metric_color(score, max_score=10):
    pct = (score / max_score) * 100
    if pct >= 80:
        return "#10b981"  # Emerald Green
    elif pct >= 60:
        return "#f59e0b"  # Amber Yellow
    else:
        return "#ef4444"  # Coral Red


def circular_donut_html(score, max_score=10, size=38, stroke=3.5, bg_cutout="#181818"):
    """Pure CSS circular donut progress meter — completely immune to SVG sanitization."""
    color = get_metric_color(score, max_score)
    pct = max(0.0, min(100.0, (score / max_score) * 100))
    inner_size = size - (stroke * 2)
    font_size = int(size * 0.38)

    return f"""<div style="width:{size}px; height:{size}px; border-radius:50%; background:conic-gradient({color} {pct:.1f}%, #282828 {pct:.1f}% 100%); display:flex; align-items:center; justify-content:center; flex-shrink:0; box-shadow:0 2px 6px rgba(0,0,0,0.5);">
<div style="width:{inner_size}px; height:{inner_size}px; border-radius:50%; background:{bg_cutout}; display:flex; align-items:center; justify-content:center; color:#ffffff; font-weight:800; font-size:{font_size}px; font-family:ui-monospace, monospace; line-height:1;">
{score}
</div>
</div>"""


def render_cue_card(p, index):
    ep = p.get("episode", 0)
    rec_start = p.get("recommended_start", "")
    rec_end = p.get("recommended_end", "")
    duration = p.get("duration_seconds", 0)
    if rec_start and rec_end:
        try:
            from parser import ts_to_seconds
            s_sec = ts_to_seconds(rec_start)
            e_sec = ts_to_seconds(rec_end)
            if e_sec > s_sec:
                duration = round(e_sec - s_sec, 1)
        except Exception:
            pass
    total = p.get("total_score", 0)
    rank = p.get("rank", index + 1)
    one_liner = p.get("one_liner", "")

    hook = p.get("hook") or {}
    hook_score = hook.get("score", 0)
    hook_desc = hook.get("description", "")
    hook_ts = hook.get("timestamp", "")
    hook_tier = "Strong Hook" if hook_score >= 8 else ("Moderate" if hook_score >= 6 else "Needs Work")

    cliff = p.get("cliffhanger") or {}
    cliff_score = cliff.get("score", 0)
    cliff_desc = cliff.get("description", "")
    cliff_ts = cliff.get("timestamp", "")
    cliff_tier = "Strong Cliffhanger" if cliff_score >= 8 else ("Moderate" if cliff_score >= 6 else "Needs Work")

    stand_score = p.get("standalone_score", 0)
    stand_note = p.get("standalone_note", "") or "Self-contained conflict; viewer understands stakes immediately."
    stand_tier = "Self-Contained" if stand_score >= 8 else ("Context Needed" if stand_score >= 6 else "Dependent")

    total_color = get_metric_color(total, 30)
    tier_text = "Strong Cut" if total >= 26 else ("Moderate" if total >= 21 else "Weak")

    card_html = f"""
<div class="cue-card">
  <!-- Top Bar with Circular Overall Score -->
  <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:14px; padding-bottom:12px; border-bottom:1px solid #222222;">
    <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
      <span class="rank-tag">CUT #{rank:02d}</span>
      <span class="ep-tag">Episode {ep:02d}</span>
      <span class="time-tag">
        <span style="font-weight:800; color:#ffffff;">{rec_start}</span>
        <span style="color:#888888; margin:0 6px;">→</span>
        <span style="font-weight:800; color:#ffffff;">{rec_end}</span>
        <span style="background:#ea1d24; color:#ffffff; font-weight:700; font-size:11px; padding:2px 7px; border-radius:4px; margin-left:8px;">{duration}s</span>
      </span>
    </div>
    
    <!-- Overall Circular Score Donut -->
    <div style="display:flex; align-items:center; gap:12px;">
      <div style="display:flex; flex-direction:column; align-items:flex-end;">
        <span style="font-size:11px; font-weight:700; color:#e5e5e5; text-transform:uppercase; letter-spacing:0.5px;">Overall Score</span>
        <span style="font-size:13px; font-weight:800; color:{total_color};">{tier_text} ({total}/30)</span>
      </div>
      {circular_donut_html(total, 30, size=48, stroke=4.5, bg_cutout="#121212")}
    </div>
  </div>

  <!-- Editorial Rationale -->
  <div style="font-size:14px; color:#ffffff; font-style:italic; margin-bottom:14px; line-height:1.6; padding:10px 14px; background:#161616; border-radius:6px; border:1px solid #242424; border-left:3px solid #ea1d24;">
    "{one_liner}"
  </div>

  <!-- Two-Column Dramatic Beats with Circular Progress Meters -->
  <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:14px;">
    
    <!-- Beat 1: Hook -->
    <div class="beat-block">
      <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px; padding-bottom:8px; border-bottom:1px solid #262626;">
        {circular_donut_html(hook_score, 10, size=38, stroke=3.5, bg_cutout="#181818")}
        <div>
          <div class="beat-label" style="color:#38bdf8; margin-bottom:2px;">01. Opening Hook (0-3s)</div>
          <div style="font-size:11px; font-weight:700; color:{get_metric_color(hook_score, 10)};">{hook_score}/10 • {hook_tier}</div>
        </div>
      </div>
      <div class="beat-text">
        <b style="color:#ffffff; font-weight:800; background:#222222; padding:2px 7px; border-radius:4px; font-family:ui-monospace, monospace; margin-right:4px;">@ {hook_ts}</b> {hook_desc}
      </div>
    </div>

    <!-- Beat 2: Cliffhanger -->
    <div class="beat-block">
      <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px; padding-bottom:8px; border-bottom:1px solid #262626;">
        {circular_donut_html(cliff_score, 10, size=38, stroke=3.5, bg_cutout="#181818")}
        <div>
          <div class="beat-label" style="color:#ea1d24; margin-bottom:2px;">02. Cliffhanger Cut Point</div>
          <div style="font-size:11px; font-weight:700; color:{get_metric_color(cliff_score, 10)};">{cliff_score}/10 • {cliff_tier}</div>
        </div>
      </div>
      <div class="beat-text">
        <b style="color:#ffffff; font-weight:800; background:#222222; padding:2px 7px; border-radius:4px; font-family:ui-monospace, monospace; margin-right:4px;">@ {cliff_ts}</b> {cliff_desc}
      </div>
    </div>

  </div>

  <!-- Standalone Watchability Footer with Mini Circular Donut -->
  <div style="margin-top:14px; padding-top:12px; border-top:1px solid #222222; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
    <div style="display:flex; align-items:center; gap:12px; width:100%;">
      {circular_donut_html(stand_score, 10, size=34, stroke=3.2, bg_cutout="#121212")}
      <div style="flex:1;">
        <div style="font-size:11px; font-weight:800; color:#e5e5e5; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:3px;">
          Standalone Context • <span style="color:{get_metric_color(stand_score, 10)}; font-weight:800;">{stand_score}/10 • {stand_tier}</span>
        </div>
        <div style="font-size:13px; color:#ffffff; line-height:1.5;">{stand_note}</div>
      </div>
    </div>
  </div>
</div>
"""
    st.html(card_html)


# ── Live Script Evaluator ───────────────────────────────────────────────────

def evaluate_single_file(uploaded_file, api_key: str):
    content = uploaded_file.read().decode("utf-8")
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
        f.write(content)
        tmp_path = f.name

    with st.spinner("Parsing timecodes and scoring candidate promo windows..."):
        ep = parse_episode(tmp_path)
        ep["episode_num"] = ep.get("episode_num") or 1
        windows = build_windows([ep], min_dur=20.0, max_dur=65.0)

        if not windows:
            st.warning("No contiguous scene windows between 20s and 65s found in this screenplay.")
            Path(tmp_path).unlink(missing_ok=True)
            return

        scored = score_windows(windows, api_key=api_key, max_windows=min(5, len(windows)), delay=2.0)

    Path(tmp_path).unlink(missing_ok=True)

    formatted = []
    for rank, w in enumerate(scored, 1):
        sc = w.get("score") or {}
        if not sc:
            continue
        formatted.append({
            "rank": rank,
            "episode": w["episode_num"],
            "recommended_start": sc.get("best_start", seconds_to_ts(w["window_start"])),
            "recommended_end": sc.get("best_end", seconds_to_ts(w["window_end"])),
            "duration_seconds": round(w["duration"], 1),
            "hook": {"score": sc.get("hook_score", 0), "description": sc.get("hook_desc", ""), "timestamp": sc.get("hook_timestamp", "")},
            "cliffhanger": {"score": sc.get("cliffhanger_score", 0), "description": sc.get("cliffhanger_desc", ""), "timestamp": sc.get("cliffhanger_timestamp", "")},
            "standalone_score": sc.get("standalone_score", 0),
            "standalone_note": sc.get("standalone_note", ""),
            "total_score": sc.get("total_score", 0),
            "one_liner": sc.get("one_liner", "")
        })

    if not formatted:
        st.error("Evaluation finished, but could not retrieve valid score ratings from the model. Please check your API key quota or update your key in ⚙️ Settings.")
        st.info("💡 Note: Google Gemini Free Tier limits keys to 20 requests/day. If your quota is exhausted, you can inspect the full verified results in the 'Identified Cuts' tab or paste an active key in ⚙️ Settings (sidebar).")
        return

    st.markdown("### Discovered Cuts for Uploaded Screenplay")
    for idx, p in enumerate(formatted):
        render_cue_card(p, idx)


# ── Main Application ────────────────────────────────────────────────────────

def main():
    promos = load_promos()

    # ── Clean Sidebar ───────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### Kuku Promo Finder")
        st.caption(f"Show: *{SHOW_TITLE}*")
        st.markdown(f"""
        <div style="display:inline-block; padding:4px 9px; background:#181818; border:1px solid #2e2e2e; border-radius:5px; font-size:11px; font-weight:700; color:#e2e8f0; margin-bottom:6px;">
            50 EPISODES PARSED • {len(promos)} RANKED CUTS
        </div>
        """, unsafe_allow_html=True)
        st.caption("Top-of-funnel ad cuts selected from full catalog analysis, ranked by 3s thumb-stop hook and cliffhanger tension.")
        st.markdown("---")

        ep_options = ["All Episodes"] + sorted(set(p["episode"] for p in promos))
        selected_ep = st.selectbox("Filter Episode", ep_options)

        sort_choice = st.selectbox("Sort By", [
            "Overall Score",
            "Opening Hook (First 3s)",
            "Cliffhanger Tension"
        ])

        min_score = st.slider("Min Score Filter", 15, 30, 22, step=1)
        st.markdown("---")

        with st.expander("⚙️ Settings", expanded=False):
            confidential_mode = st.toggle(
                "🔒 Confidential Mode",
                value=False,
                help="Forces 100% on-device processing. No screenplay text is sent to external cloud APIs."
            )
            if confidential_mode:
                st.caption("🔒 Active: External cloud API calls are completely disabled. Evaluating locally via Deterministic Drama Engine.")
                active_api_key = ""
            else:
                if "custom_api_key" not in st.session_state:
                    st.session_state["custom_api_key"] = ""

                new_key = st.text_input(
                    "Gemini API Key",
                    type="password",
                    value=st.session_state["custom_api_key"],
                    placeholder="Enter API key...",
                )
                if st.button("Save", use_container_width=True):
                    st.session_state["custom_api_key"] = new_key.strip()
                    st.toast("API key updated")

                active_api_key = st.session_state.get("custom_api_key") or os.getenv("GEMINI_API_KEY", "").strip()

    # ── Main Header ─────────────────────────────────────────────────────────
    st.markdown("## Promo Cue Sheet")
    st.caption("20 to 60-second ad cuts identified from screenplay timecodes, ranked by hook strength and cliffhanger tension.")
    st.markdown("<div style='margin-bottom:12px;'></div>", unsafe_allow_html=True)

    tab_browse, tab_test = st.tabs(["Identified Cuts", "Evaluate New Script"])

    # ── Tab 1: Promo Cuts ───────────────────────────────────────────────────
    with tab_browse:
        filtered = [p for p in promos if p.get("total_score", 0) >= min_score]
        if selected_ep != "All Episodes":
            filtered = [p for p in filtered if p.get("episode") == selected_ep]

        if sort_choice == "Opening Hook (First 3s)":
            filtered = sorted(filtered, key=lambda p: (p.get("hook") or {}).get("score", 0), reverse=True)
        elif sort_choice == "Cliffhanger Tension":
            filtered = sorted(filtered, key=lambda p: (p.get("cliffhanger") or {}).get("score", 0), reverse=True)
        else:
            filtered = sorted(filtered, key=lambda p: p.get("total_score", 0), reverse=True)

        import csv
        import io
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(["Rank", "Episode", "Start Time", "End Time", "Duration (s)", "Overall Score", "Hook (0-10)", "Hook Description", "Cliffhanger (0-10)", "Cliffhanger Description", "Standalone (0-10)", "Editorial Rationale"])
        for p in filtered:
            writer.writerow([
                p.get("rank"),
                f"Episode {p.get('episode'):02d}" if isinstance(p.get("episode"), int) else p.get("episode"),
                p.get("recommended_start"),
                p.get("recommended_end"),
                p.get("duration_seconds"),
                p.get("total_score"),
                (p.get("hook") or {}).get("score", 0),
                (p.get("hook") or {}).get("description", ""),
                (p.get("cliffhanger") or {}).get("score", 0),
                (p.get("cliffhanger") or {}).get("description", ""),
                p.get("standalone_score", 0),
                p.get("one_liner", ""),
            ])

        col_count, col_dl = st.columns([3, 1])
        with col_count:
            st.markdown(f"<div style='color:#cbd5e1; font-size:13px; padding-top:6px;'>Showing <b style='color:#ffffff;'>{len(filtered)}</b> qualified cuts (Score threshold: <span style='color:#38bdf8; font-weight:700;'>{min_score}+</span>)</div>", unsafe_allow_html=True)
        with col_dl:
            st.download_button(
                label="📥 Export CSV Cue Sheet",
                data=csv_buffer.getvalue(),
                file_name="kuku_promos_cuesheet.csv",
                mime="text/csv",
                use_container_width=True,
            )
        st.markdown("<div style='margin-bottom:10px;'></div>", unsafe_allow_html=True)

        for idx, p in enumerate(filtered):
            render_cue_card(p, idx)

    # ── Tab 2: Test New Script ──────────────────────────────────────────────
    with tab_test:
        st.markdown("#### Test Screenplay File")
        st.caption("Upload a microdrama screenplay `.txt` to parse scenes and evaluate candidate ad cuts.")

        uploaded = st.file_uploader("Upload screenplay .txt", type=["txt"], label_visibility="collapsed")
        if uploaded:
            if confidential_mode:
                st.info("🔒 Confidential Mode Active: Evaluating 100% on-device (Zero external API calls).")
            elif not active_api_key:
                st.info("ℹ️ Running in Deterministic Mode (evaluating with code heuristics). To score with Gemini Flash, enter an API key in ⚙️ Settings.")
            evaluate_single_file(uploaded, active_api_key)


if __name__ == "__main__":
    main()
