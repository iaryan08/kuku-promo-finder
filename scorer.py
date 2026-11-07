"""
scorer.py — Kuku Promo Finder
Sends parsed scene windows to Gemini 3.8 Flash (with automatic cascade) and scores them for promo potential.
"""

import json
import os
import time
from google import genai
from google.genai import types


SYSTEM_PROMPT = """You are an expert social media editor for a microdrama streaming platform.
Your job is to identify the best promotional clips from show screenplays.

A great promo (20–60 seconds) must:
1. HOOK (first 3 seconds): Something that makes a scrolling viewer stop — a slap, shocking reveal, betrayal, or explosive line
2. CLIFFHANGER (end): Cut at an unresolved moment so the viewer MUST know what happens next
3. SELF-CONTAINED: Make sense to someone who has never seen the show before

You will receive a window of scenes/events from a screenplay. Score it and extract the best promo segment from within it.
Always return valid JSON only — no markdown, no explanation outside the JSON."""


SCORE_PROMPT = """Analyze this screenplay excerpt and score it as a potential promo clip.

SHOW: {show_title}
EPISODE: {episode_num}
WINDOW DURATION: {duration:.1f} seconds ({start_ts} → {end_ts})

--- SCREENPLAY EXCERPT ---
{content}
--- END ---

Return a JSON object with EXACTLY this structure:
{{
  "hook_score": <int 0-10>,
  "hook_desc": "<what the hook moment is, or 'none' if no hook>",
  "hook_timestamp": "<MM:SS.ss of the hook moment>",
  "cliffhanger_score": <int 0-10>,
  "cliffhanger_desc": "<what the cliffhanger is, or 'none' if no cliffhanger>",
  "cliffhanger_timestamp": "<MM:SS.ss of the best cut point>",
  "standalone_score": <int 0-10>,
  "standalone_note": "<one line: does it make sense to a new viewer?>",
  "best_start": "<MM:SS.ss — recommended promo start within this window>",
  "best_end": "<MM:SS.ss — recommended promo end within this window>",
  "one_liner": "<one sentence: why this promo works or doesn't>",
  "total_score": <int 0-30, sum of above three scores>
}}"""


def seconds_to_ts(s: float) -> str:
    """Convert float seconds to MM:SS.ss string."""
    m = int(s // 60)
    sec = s - m * 60
    return f"{m:02d}:{sec:05.2f}"


def format_window_content(events: list) -> str:
    """Format a list of events into readable screenplay text for the LLM."""
    lines = []
    for ev in events:
        ts = seconds_to_ts(ev["start"])
        if ev["type"] == "DIALOGUE":
            speaker = ev.get("speaker", "UNKNOWN")
            emotion = ev.get("emotion", "")
            em_str = f" ({emotion})" if emotion else ""
            lines.append(f"[{ts}] {speaker}{em_str}: \"{ev['text']}\"")
        elif ev["type"] == "ACTION":
            lines.append(f"[{ts}] ACTION: {ev['text'][:120]}")
        elif ev["type"] == "CAMERA":
            lines.append(f"[{ts}] CAMERA: {ev['text'][:80]}")
    return "\n".join(lines)


def build_windows(episodes: list, min_dur: float = 20.0, max_dur: float = 60.0,
                  step: float = 15.0) -> list:
    """
    Build candidate promo windows across episodes using both scene combinations
    and sub-scene sliding windows across events (essential for microdramas where
    single scenes exceed 60 seconds).

    Returns list of window dicts:
    {
      "episode_num": int,
      "window_start": float,
      "window_end": float,
      "duration": float,
      "scenes": [...],
      "events": [...],
      "content": str   # formatted for LLM
    }
    """
    windows = []

    for ep in episodes:
        scenes = ep.get("scenes", [])
        n = len(scenes)
        ep_wins = []

        # 1. Whole-scene combinations (for short adjacent scenes)
        for i in range(n):
            start_scene = scenes[i]
            window_start = start_scene["start"]
            accumulated_events = []

            for j in range(i, n):
                end_scene = scenes[j]
                window_end = end_scene["end"]
                duration = window_end - window_start
                accumulated_events.extend(end_scene.get("events", []))

                if duration < min_dur:
                    continue
                if duration > max_dur:
                    break

                content = format_window_content(accumulated_events)
                ep_wins.append({
                    "episode_num": ep["episode_num"],
                    "window_start": window_start,
                    "window_end": window_end,
                    "duration": duration,
                    "scenes": [s["scene_id"] for s in scenes[i:j+1]],
                    "events": accumulated_events.copy(),
                    "content": content,
                })

        # 2. Sub-scene sliding windows across events for long scenes (or if few windows found)
        for sc in scenes:
            sc_dur = sc["end"] - sc["start"]
            events = sc.get("events", [])
            if sc_dur < min_dur or not events:
                continue

            # If scene is longer than max_dur or we don't have enough windows for this episode
            if sc_dur > max_dur or len(ep_wins) < 3:
                cur_t = sc["start"]
                while cur_t + min_dur <= sc["end"]:
                    for target_len in [30.0, 45.0, 60.0]:
                        target_end = min(cur_t + target_len, sc["end"])
                        if (target_end - cur_t) < min_dur:
                            continue

                        sub_evs = [e for e in events if e["end"] >= cur_t and e["start"] <= target_end]
                        if len(sub_evs) >= 2:
                            w_start = min(e["start"] for e in sub_evs)
                            w_end = max(e["end"] for e in sub_evs)
                            w_dur = w_end - w_start

                            if min_dur <= w_dur <= max_dur:
                                # Deduplicate candidates within 4 seconds of existing windows
                                if not any(abs(w["window_start"] - w_start) < 4.0 and abs(w["window_end"] - w_end) < 4.0 for w in ep_wins):
                                    content = format_window_content(sub_evs)
                                    ep_wins.append({
                                        "episode_num": ep["episode_num"],
                                        "window_start": w_start,
                                        "window_end": w_end,
                                        "duration": w_dur,
                                        "scenes": [sc["scene_id"]],
                                        "events": sub_evs,
                                        "content": content,
                                    })
                    cur_t += step

        windows.extend(ep_wins)

    print(f"Built {len(windows)} candidate windows across {len(episodes)} episodes.")
    return windows


# Model priority list — gemini-3.8-flash primary, followed by fallback models
DEFAULT_MODEL_CASCADE = [
    "gemini-3.8-flash",         # Primary evaluator (recommended by Google API endpoint)
    "gemini-3.6-flash",         # Verified working Flash
    "gemini-2.5-flash",         # Verified working Flash
    "gemini-3.5-flash",         # Verified working Flash
    "gemini-pro-latest",        # Verified working Pro fallback
]


def heuristic_score_window(w: dict) -> dict:
    """
    Deterministic Drama Heuristic Engine (pure code, zero API calls).
    Evaluates candidate windows using conflict keyword density, speech volatility,
    and microdrama tension tropes. Serves as both an offline fallback and a pre-filter.
    """
    content = w.get("content", "").lower()
    events = w.get("events", [])

    # 1. Hook tension cues (first 3s volatility)
    hook_keywords = [
        "slap", "betray", "wedding", "bride", "altar", "execution", "kill",
        "poison", "fire", "sword", "knife", "gasp", "screams", "mock",
        "bastard", "liar", "ruin", "blood", "tear", "arrest", "guards", "shouts"
    ]
    hook_matches = [k for k in hook_keywords if k in content]
    hook_score = min(10, 6 + len(hook_matches))

    # 2. Cliffhanger cues (unresolved cut-off, orders, sudden danger)
    cliff_keywords = [
        "wait", "stop", "never", "who", "how", "die", "mine", "burn",
        "dungeon", "iron", "drag", "dead", "witch", "take her", "seize", "listen"
    ]
    cliff_matches = [k for k in cliff_keywords if k in content]
    cliff_score = min(10, 6 + len(cliff_matches))

    # 3. Standalone comprehension (dialogue balance across 2-3 characters)
    speakers = set()
    for ev in events:
        if ev.get("speaker"):
            speakers.add(ev["speaker"])
    standalone_score = 9 if len(speakers) in (2, 3) else 8
    total_score = hook_score + cliff_score + standalone_score

    start_ts = seconds_to_ts(w["window_start"])
    end_ts = seconds_to_ts(w["window_end"])

    hook_desc = f"Dramatic conflict detected ({', '.join(hook_matches[:2])})" if hook_matches else "Opening confrontation between characters."
    cliff_desc = f"Cut on unresolved tension ({', '.join(cliff_matches[:2])})" if cliff_matches else "High-stakes cutoff before resolution."
    one_liner = f"High-tension candidate cut with {len(speakers)} characters and rapid dialogue momentum."

    return {
        "hook_score": hook_score,
        "hook_desc": hook_desc,
        "hook_timestamp": start_ts,
        "cliffhanger_score": cliff_score,
        "cliffhanger_desc": cliff_desc,
        "cliffhanger_timestamp": end_ts,
        "standalone_score": standalone_score,
        "standalone_note": "Self-contained conflict clearly recognizable without full backstory.",
        "best_start": start_ts,
        "best_end": end_ts,
        "one_liner": one_liner,
        "total_score": total_score,
        "evaluated_by": "deterministic-heuristic-engine"
    }


def score_windows(windows: list, api_key: str = "", show_title: str = "I Married a Broken Soldier",
                  max_windows: int = None, delay: float = 12.5,
                  model_cascade: list = None) -> list:
    """
    Score candidate windows using Gemini with automatic fallback on quota limits.
    Tries primary model first; if 429/quota limit is hit, cascades down.
    If no API key is provided, gracefully uses the Deterministic Drama Heuristic Engine.
    """
    if max_windows and len(windows) > max_windows:
        step = len(windows) / max_windows
        indices = [int(i * step) for i in range(max_windows)]
        windows_to_score = [windows[i] for i in indices]
    else:
        windows_to_score = windows

    # Offline / No-API-key fallback: use Deterministic Drama Heuristic Engine directly
    if not api_key:
        print("\n⚡ No API key provided. Evaluating with Deterministic Drama Heuristic Engine...", flush=True)
        scored = []
        for w in windows_to_score:
            h = heuristic_score_window(w)
            w["score"] = h
            w["total_score"] = h["total_score"]
            w["evaluated_by_model"] = "deterministic-heuristic-engine"
            scored.append(w)
        scored.sort(key=lambda x: x.get("total_score", 0), reverse=True)
        return scored

    client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})
    cascade = model_cascade or list(DEFAULT_MODEL_CASCADE)
    active_model_idx = 0

    scored = []
    total = len(windows_to_score)

    print(f"\nScoring {total} windows with AI Evaluator (Primary: {cascade[0]})...", flush=True)
    print(f"Fallback cascade: {' -> '.join(cascade)}", flush=True)
    print(f"Estimated time: ~{total * delay / 60:.1f} minutes\n", flush=True)

    for idx, w in enumerate(windows_to_score):
        ep = w["episode_num"]
        start_ts = seconds_to_ts(w["window_start"])
        end_ts = seconds_to_ts(w["window_end"])

        prompt = SCORE_PROMPT.format(
            show_title=show_title,
            episode_num=ep,
            duration=w["duration"],
            start_ts=start_ts,
            end_ts=end_ts,
            content=w["content"],
        )

        success = False
        while active_model_idx < len(cascade) and not success:
            current_model = cascade[active_model_idx]
            max_retries = 2

            for attempt in range(max_retries):
                try:
                    response = client.models.generate_content(
                        model=current_model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_PROMPT,
                            temperature=0.2,
                            response_mime_type="application/json",
                        ),
                    )
                    raw_text = response.text.strip()
                    if raw_text.startswith("```json"):
                        raw_text = raw_text[7:]
                    if raw_text.startswith("```"):
                        raw_text = raw_text[3:]
                    if raw_text.endswith("```"):
                        raw_text = raw_text[:-3]

                    result = json.loads(raw_text.strip())
                    w["score"] = result
                    w["total_score"] = result.get("total_score", 0)
                    w["evaluated_by_model"] = current_model
                    scored.append(w)

                    print(f"  [{idx+1}/{total}] Ep {ep:02d} {start_ts}→{end_ts} "
                          f"| score={result.get('total_score', '?'):>2} "
                          f"| hook={result.get('hook_score','?')} "
                          f"cliff={result.get('cliffhanger_score','?')} "
                          f"stand={result.get('standalone_score','?')} "
                          f"[{current_model}]", flush=True)
                    success = True
                    break

                except json.JSONDecodeError as e:
                    print(f"  [{idx+1}/{total}] Ep {ep:02d} JSON parse error: {e}", flush=True)
                    w["score"] = None
                    w["total_score"] = 0
                    scored.append(w)
                    success = True  # Move on
                    break

                except Exception as e:
                    err_str = str(e)
                    # Quota / Model exhaustion: cascade to next fallback model immediately!
                    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "404" in err_str:
                        print(f"  ⚠️ {current_model} quota limit hit ({err_str[:45]}...).", flush=True)
                        active_model_idx += 1
                        if active_model_idx < len(cascade):
                            print(f"  🔄 Gracefully falling back to {cascade[active_model_idx]}...", flush=True)
                        break  # Break retry loop to try next model in cascade
                    # Transient spike (503): wait and retry
                    elif ("503" in err_str or "UNAVAILABLE" in err_str) and attempt < max_retries - 1:
                        wait_sec = 4.0 * (attempt + 1)
                        print(f"  [{idx+1}/{total}] Ep {ep:02d} temporary 503 spike, retrying in {wait_sec}s...", flush=True)
                        time.sleep(wait_sec)
                    else:
                        print(f"  [{idx+1}/{total}] Ep {ep:02d} error on {current_model}: {err_str[:60]}", flush=True)
                        active_model_idx += 1
                        if active_model_idx < len(cascade):
                            print(f"  🔄 Cascading to {cascade[active_model_idx]}...", flush=True)
                        break

        if not success and active_model_idx >= len(cascade):
            print(f"  ⚡ API quota exhausted. Activating Deterministic Drama Heuristic Engine for Ep {ep:02d} {start_ts}→{end_ts}...", flush=True)
            h_score = heuristic_score_window(w)
            w["score"] = h_score
            w["total_score"] = h_score["total_score"]
            w["evaluated_by_model"] = "deterministic-heuristic-engine"
            scored.append(w)

        # Rate limit delay between windows
        if idx < total - 1:
            time.sleep(delay)

    # Sort by total score descending
    scored.sort(key=lambda x: x.get("total_score", 0), reverse=True)
    return scored
