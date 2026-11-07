"""
run.py — Kuku Promo Finder
Main entry point: auto-detect input → parse → score → rank → save raw outputs.

Usage:
  python run.py                              # auto-detect from data/
  python run.py --input path/to/folder      # explicit folder
  python run.py --input path/to/pack.zip    # auto-unzip
  python run.py --max-windows 40            # faster run (fewer API calls)
"""

import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv

from input_loader import resolve_input_folder, parse_args
from parser import load_all_episodes
from scorer import build_windows, score_windows, seconds_to_ts


def ts_to_seconds(ts: str) -> float:
    """Convert MM:SS.ss timestamp string to float seconds."""
    m = re.match(r"(\d+):(\d+(?:\.\d+)?)", ts)
    if not m:
        return 0.0
    return int(m.group(1)) * 60 + float(m.group(2))

load_dotenv()

SHOW_TITLE = "I Married a Broken Soldier. He was a Duke"


def rank_promos(scored_windows: list, top_n: int = 20) -> list:
    """Return top N non-overlapping promos across all episodes."""
    seen = set()
    ranked = []
    for w in scored_windows:
        if w.get("total_score", 0) == 0:
            continue
        # Deduplicate by episode + 10s bucket to avoid near-identical windows
        key = (w["episode_num"], round(w["window_start"] / 10))
        if key in seen:
            continue
        seen.add(key)
        ranked.append(w)
        if len(ranked) >= top_n:
            break
    return ranked


def build_output(ranked: list, show_title: str, min_clip_dur: float = 20.0) -> dict:
    """Build the final structured output dict for JSON export.

    Post-filter: if the LLM's recommended sub-window is shorter than min_clip_dur,
    fall back to the full window timestamps so every published clip is in-spec.
    """
    promos = []
    for rank, w in enumerate(ranked, 1):
        sc = w.get("score") or {}

        # Resolve recommended start/end, with fallback to window timestamps
        rec_start = sc.get("best_start", seconds_to_ts(w["window_start"]))
        rec_end   = sc.get("best_end",   seconds_to_ts(w["window_end"]))

        # Enforce minimum clip duration — reject sub-windows the LLM trimmed too far
        clip_dur = ts_to_seconds(rec_end) - ts_to_seconds(rec_start)
        if clip_dur < min_clip_dur:
            rec_start = seconds_to_ts(w["window_start"])
            rec_end   = seconds_to_ts(w["window_end"])

        promos.append({
            "rank": rank,
            "episode": w["episode_num"],
            "window_start": seconds_to_ts(w["window_start"]),
            "window_end": seconds_to_ts(w["window_end"]),
            "duration_seconds": round(w["duration"], 1),
            "scenes_covered": w["scenes"],
            "recommended_start": rec_start,
            "recommended_end":   rec_end,
            "hook": {
                "score":       sc.get("hook_score", 0),
                "description": sc.get("hook_desc", ""),
                "timestamp":   sc.get("hook_timestamp", ""),
            },
            "cliffhanger": {
                "score":       sc.get("cliffhanger_score", 0),
                "description": sc.get("cliffhanger_desc", ""),
                "timestamp":   sc.get("cliffhanger_timestamp", ""),
            },
            "standalone_score": sc.get("standalone_score", 0),
            "standalone_note":  sc.get("standalone_note", ""),
            "total_score":      sc.get("total_score", 0),
            "one_liner":        sc.get("one_liner", ""),
            "evaluated_by_model": w.get("evaluated_by_model", ""),
        })
    return {"show": show_title, "total_promos_found": len(promos), "promos": promos}


def main():
    args = parse_args()
    api_key = os.getenv("GEMINI_API_KEY", "")

    if args.confidential:
        api_key = ""
        print("\n" + "=" * 60)
        print("🔒 CONFIDENTIAL MODE ACTIVE (100% On-Device)")
        print("   Zero cloud calls: All evaluations run via local Drama Engine.")
        print("=" * 60 + "\n")
    elif not api_key:
        print("\n💡 Notice: GEMINI_API_KEY not set or quota exhausted.")
        print("   -> Automatically activating Offline Deterministic Mode (Zero API calls).")
        print("   -> Scoring candidate windows using the internal Drama Heuristic Engine.\n")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # ── Step 1: Resolve input ────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 1: Locating episode data...")
    print("=" * 60)
    episodes_folder = resolve_input_folder(args.input)
    print(f"  📂 Episodes folder: {episodes_folder}\n")

    # ── Step 2: Parse ────────────────────────────────────────────────────────
    print("=" * 60)
    print("STEP 2: Parsing screenplays...")
    print("=" * 60)
    episodes = load_all_episodes(str(episodes_folder))
    print(f"\n✓ Loaded {len(episodes)} episodes.")

    # Save parse summary
    summary = [{
        "episode_num":    ep["episode_num"],
        "logline":        ep["logline"],
        "num_scenes":     len(ep["scenes"]),
        "total_duration": ep["scenes"][-1]["end"] if ep["scenes"] else 0,
    } for ep in episodes]
    with open(output_dir / "parsed_episodes.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # ── Step 3: Build windows ────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 3: Building candidate promo windows...")
    print("=" * 60)
    windows = build_windows(episodes, min_dur=20.0, max_dur=60.0)
    print(f"✓ {len(windows)} candidate windows built.")

    # ── Step 4: Score with Gemini ────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"STEP 4: Scoring with Gemini Flash (max {args.max_windows} windows)...")
    print("=" * 60)
    scored = score_windows(
        windows,
        api_key=api_key,
        show_title=SHOW_TITLE,
        max_windows=args.max_windows,
    )

    # Save raw scored windows (unedited — required deliverable)
    slim = [{k: v for k, v in w.items() if k not in ("events", "content")} for w in scored]
    with open(output_dir / "scored_windows.json", "w", encoding="utf-8") as f:
        json.dump(slim, f, indent=2)
    print(f"\n✓ Raw scores saved → {output_dir}/scored_windows.json")

    # ── Step 5: Rank & output ────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"STEP 5: Ranking top {args.top_n} promos...")
    print("=" * 60)
    ranked = rank_promos(scored, top_n=args.top_n)
    output  = build_output(ranked, SHOW_TITLE)

    with open(output_dir / "promos.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    # ── Print results ────────────────────────────────────────────────────────
    print(f"\n✅ Found {len(ranked)} promos. Top 10:\n")
    for p in output["promos"][:10]:
        print(f"  #{p['rank']:>2} | Ep {p['episode']:02d} | "
              f"{p['recommended_start']} → {p['recommended_end']} "
              f"| Score {p['total_score']:>2}/30")
        print(f"       🪝  Hook     : {p['hook']['description'][:72]}")
        print(f"       ⛰️  Cliff    : {p['cliffhanger']['description'][:72]}")
        print(f"       💬  Why     : {p['one_liner'][:72]}\n")

    print(f"📁 Raw outputs → {output_dir.resolve()}")
    print("   promos.json          ← final ranked promos (submit this)")
    print("   scored_windows.json  ← all scored windows (unedited)")
    print("   parsed_episodes.json ← parse summary")
    print("\n🚀 To launch the UI:  streamlit run app.py\n")


if __name__ == "__main__":
    main()
