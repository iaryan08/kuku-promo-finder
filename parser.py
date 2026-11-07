"""
parser.py — Kuku Promo Finder
Parses Kuku microdrama .txt screenplays into structured scene/event data.
"""

import re
import os
from pathlib import Path


def ts_to_seconds(ts: str) -> float:
    """Convert 'MM:SS.ss' or 'SS.ss' timestamp string to float seconds."""
    ts = ts.strip()
    if ":" in ts:
        parts = ts.split(":")
        return float(parts[0]) * 60 + float(parts[1])
    return float(ts)


def parse_episode(filepath: str) -> dict:
    """
    Parse a single episode .txt file into structured data.

    Returns:
        {
          "episode_num": int,
          "logline": str,
          "continuity": str,
          "scenes": [
            {
              "scene_id": "01",
              "heading": "INT. CATHEDRAL – DAY",
              "start": 0.0,   # seconds
              "end": 138.0,
              "events": [
                {
                  "type": "DIALOGUE" | "ACTION" | "CAMERA",
                  "speaker": str | None,
                  "emotion": str | None,
                  "text": str,
                  "start": float,
                  "end": float,
                }
              ]
            }
          ]
        }
    """
    with open(filepath, encoding="utf-8") as f:
        raw = f.read()

    # ── Episode header ──────────────────────────────────────────────────────
    ep_num_match = re.search(r"EPISODE NUMBER:\s*Episode\s*(\d+)", raw, re.IGNORECASE)
    logline_match = re.search(r"EPISODE LOGLINE:\s*(.+)", raw, re.IGNORECASE)
    continuity_match = re.search(r"CONTINUITY NOTES:\s*(.+)", raw, re.IGNORECASE)

    episode_num = int(ep_num_match.group(1)) if ep_num_match else 0
    logline = logline_match.group(1).strip() if logline_match else ""
    continuity = continuity_match.group(1).strip() if continuity_match else ""

    # ── Split into scenes ───────────────────────────────────────────────────
    # Each scene block starts with "SCENE NN" (case-insensitive)
    scene_blocks = re.split(r"\n{1,2}(?=SCENE \d+)", raw, flags=re.IGNORECASE)
    scenes = []

    for block in scene_blocks:
        scene_id_match = re.match(r"SCENE (\d+)", block, re.IGNORECASE)
        if not scene_id_match:
            continue

        scene_id = scene_id_match.group(1)
        heading_match = re.search(r"Scene heading:\s*(.+)", block, re.IGNORECASE)
        scene_start_match = re.search(r"Scene start:\s*([\d:.]+)", block, re.IGNORECASE)
        scene_end_match = re.search(r"Scene end:\s*([\d:.]+)", block, re.IGNORECASE)

        heading = heading_match.group(1).strip() if heading_match else ""
        scene_start = ts_to_seconds(scene_start_match.group(1)) if scene_start_match else 0.0
        scene_end = ts_to_seconds(scene_end_match.group(1)) if scene_end_match else 0.0

        events = _parse_events(block)

        scenes.append({
            "scene_id": scene_id,
            "heading": heading,
            "start": scene_start,
            "end": scene_end,
            "events": events,
        })

    # Fallback: if no SCENE headers found, extract events from entire file
    if not scenes:
        fallback_events = _parse_events(raw)
        if fallback_events:
            scenes.append({
                "scene_id": "01",
                "heading": "SCENE 01",
                "start": min(e["start"] for e in fallback_events),
                "end": max(e["end"] for e in fallback_events),
                "events": fallback_events,
            })

    return {
        "episode_num": episode_num,
        "logline": logline,
        "continuity": continuity,
        "filepath": str(filepath),
        "scenes": scenes,
    }


def _parse_events(block: str) -> list:
    """Extract all timestamped events (DIALOGUE, ACTION, CAMERA) from a scene block."""
    events = []

    # Pattern: **SPEAKER (Emotion):** or **ACTION:** or **CAMERA:**
    # Followed by Start: (MM:SS.ss) | End: (MM:SS.ss)
    # Then the actual text on the next line(s)

    # Split block into chunks by bold headers **...**
    chunks = re.split(r"\n(?=\*\*)", block)

    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk.startswith("**"):
            continue

        # Determine type
        header_match = re.match(r"\*\*(.+?)\*\*:?", chunk)
        if not header_match:
            continue
        header = header_match.group(1).strip()

        # Timestamps
        start_match = re.search(r"Start:\s*\(([\d:.]+)\)", chunk, re.IGNORECASE)
        end_match = re.search(r"End:\s*\(([\d:.]+)\)", chunk, re.IGNORECASE)
        if not start_match or not end_match:
            continue

        evt_start = ts_to_seconds(start_match.group(1))
        evt_end = ts_to_seconds(end_match.group(1))

        # Text content (last quoted line or action description)
        # Look for quoted dialogue first
        dialogue_match = re.search(r'"(.+?)"', chunk, re.DOTALL)
        # Fallback: last non-empty non-timestamp line
        text_lines = [
            l.strip() for l in chunk.split("\n")
            if l.strip()
            and not l.strip().startswith("**")
            and not l.strip().startswith("Start:")
            and not l.strip().startswith("End:")
        ]
        text = dialogue_match.group(1).strip() if dialogue_match else (
            text_lines[-1] if text_lines else ""
        )

        # Classify
        if header in ("ACTION", "CAMERA"):
            evt_type = header
            speaker = None
            emotion = None
        else:
            evt_type = "DIALOGUE"
            # Parse "SPEAKER NAME (Emotion, Sub-emotion)" or "SPEAKER (Off-screen) (Emotion)"
            speaker_match = re.match(r"^(.*?)(?:\s*\(Off-screen\))?\s*(?:\((.+?)\))?$", header)
            speaker = speaker_match.group(1).strip() if speaker_match else header
            emotion = speaker_match.group(2).strip() if speaker_match and speaker_match.group(2) else None

        events.append({
            "type": evt_type,
            "speaker": speaker,
            "emotion": emotion,
            "text": text,
            "start": evt_start,
            "end": evt_end,
        })

    return events


def load_all_episodes(folder: str) -> list:
    """Load and parse all .txt episode files from a folder, sorted by episode number."""
    folder = Path(folder)
    files = sorted(folder.glob("episode-*.txt"))
    episodes = []
    for f in files:
        try:
            ep = parse_episode(str(f))
            episodes.append(ep)
            print(f"  ✓ Episode {ep['episode_num']:02d} — {len(ep['scenes'])} scenes")
        except Exception as e:
            print(f"  ✗ Failed to parse {f.name}: {e}")
    return episodes


if __name__ == "__main__":
    folder = Path(__file__).parent / "data" / "I Married a Broken Soldier. He was a Duke"
    print("Parsing episodes...")
    eps = load_all_episodes(folder)
    print(f"\nLoaded {len(eps)} episodes.")
    # Quick sanity check on ep 1
    ep1 = eps[0]
    print(f"\nEpisode 1 — {len(ep1['scenes'])} scenes")
    for sc in ep1["scenes"][:3]:
        print(f"  Scene {sc['scene_id']} [{sc['start']:.1f}s – {sc['end']:.1f}s]: {sc['heading']}")
        for ev in sc["events"][:2]:
            print(f"    [{ev['type']}] {ev['start']:.1f}s: {ev['text'][:60]}")

