# kuku-promo-finder

> 🚀 **Live Interactive Demo:** [promocraft-ai.streamlit.app](https://promocraft-ai.streamlit.app/)

A Python tool that analyzes microdrama screenplays and extracts 20 to 60-second promo clips for short-form ad platforms (TikTok, Instagram Reels, YouTube Shorts). Built for the Kuku AI Generalist Assignment (Problem 1).

## Background and Motivation

Kuku releases vertical microdrama shows with dozens of 1 to 2-minute episodes weekly. Currently, video editors manually scrub through full episodes to identify ad hooks. This manual workflow creates a few clear bottlenecks:

1. Time investment: Screening 50 episodes takes roughly 2 hours per show.
2. Inconsistent criteria: Different editors prioritize different moments, making ad creative performance noisy.
3. Overlooked catalog: Editors naturally favor early episodes, leaving high-tension moments in mid-to-late episodes unmined.

This tool automates the discovery and ranking of promo segments using deterministic timecode parsing combined with targeted LLM evaluation.

## How It Works

The pipeline is split into four distinct steps:

1. Screenplay Parser (`parser.py`):
   The raw files in the dataset contain structured cues with scene headings, action descriptions, camera directions, and dialogue lines with start and end timestamps in `MM:SS.ss` format. A regex-based parser extracts these into structured scene objects with absolute second timestamps.

2. Candidate Window Generator (`scorer.py`):
   Rather than passing entire episodes to an LLM, the script slides across contiguous scene events to construct candidate windows bounded between 20.0 and 60.0 seconds. This guarantees that all candidate timestamps map strictly to real dialogue and action boundaries. Builds 565 candidate windows across all 50 episodes.

3. Structured Evaluation (`scorer.py`):
   Candidate windows are evaluated using Gemini Flash via Google's `google-genai` SDK in JSON mode. The model scores three metrics on a 0 to 10 scale:
   - Hook score: Strength of the opening 3 seconds (betrayal, confrontation, sudden conflict).
   - Cliffhanger score: Tension at the cut point before resolution occurs.
   - Standalone score: Whether a viewer who has never heard of the show understands the conflict.
   The model also outputs precise sub-window start/end recommendations and a concise rationale.

4. Ranking and Deduplication (`run.py`):
   Scored candidates are sorted by composite score. A temporal bucket deduplicator prevents near-identical overlapping windows from dominating the top recommendations.

## Resilience and Fallback

On free-tier API quotas, models often encounter rate limits (e.g. 5 RPM or daily request caps). The evaluator implements an automatic fallback cascade:
`gemini-3.8-flash -> gemini-3.6-flash -> gemini-2.5-flash -> gemini-3.5-flash -> gemini-pro-latest -> Deterministic Drama Heuristic Engine`

If the primary model returns a 429 quota error, the script logs the issue and immediately routes requests down the cascade. If all cloud API quotas are exhausted—or if `--confidential` is passed—the on-device Deterministic Drama Heuristic Engine scores all candidate windows locally with zero API calls.

## Repository Structure

```
kuku-promo-finder/
|-- app.py                  # Streamlit web interface for browsing and testing
|-- run.py                  # CLI pipeline runner
|-- parser.py               # Regex script parser
|-- scorer.py               # Window generator and LLM scoring logic
|-- input_loader.py         # Dynamic input detection (data folder, zip, or CLI flag)
|-- requirements.txt        # Dependencies
|-- .gitignore              # Ignores sensitive scripts and data/
|-- .env.example            # Environment template
|-- raw_outputs/            # Output directory
|   |-- promos.json         # Top ranked promo selections
|   |-- scored_windows.json # Raw scores for all evaluated windows
|   `-- parsed_episodes.json# Parsed episode summaries
|-- SOLUTION_DOCUMENT.md    # 2-page technical submission document
`-- data/                   # Git-ignored directory for confidential episode files
```

## Setup and Usage

### Prerequisites

- Python 3.10+
- A Google Gemini API key from Google AI Studio

### Installation

```bash
git clone https://github.com/iaryan08/kuku-promo-finder.git
cd kuku-promo-finder
pip install -r requirements.txt
```

### Configuration

Copy `.env.example` to `.env` and insert your API key:

```bash
cp .env.example .env
```

### Adding Show Data

Per Kuku's confidentiality guidelines, episode text files are not committed to Git. Place them in the `data/` directory using either approach:
- Drop the unzipped episode folder: `data/I Married a Broken Soldier. He was a Duke/`
- Or drop the raw zip file directly into `data/` (the loader auto-extracts it).

### Running the Pipeline

```bash
# Run on auto-detected data (defaults to 16 representative windows)
python run.py

# Run in 100% Confidential Mode (Zero external API calls, on-device Drama Engine)
python run.py --confidential

# Or pass custom parameters
python run.py --input path/to/episodes --max-windows 40 --top-n 10
```

### Launching the Web Interface

- **Live Cloud App:** [promocraft-ai.streamlit.app](https://promocraft-ai.streamlit.app/)
- **Local Run:** `python -m streamlit run app.py`

The Streamlit UI displays the ranked promo cards, visual breakdown of Hook vs Cliffhanger vs Standalone ratings, exact cut timecodes, and includes a live single-episode testing tab.

## Engineering Trade-offs and Limitations

1. Action vs Dialogue Disparity:
   The screenplays describe visual action in `ACTION:` blocks and spoken words in dialogue blocks. Scenes with intense physical drama (e.g. swordfights, fire rescues) but sparse dialogue often receive lower standalone scores from LLMs because the text lacks spoken exposition. A future improvement would be adding keyword-based score boosts for action verbs before LLM ingestion.

2. Single-Episode Boundary:
   Current candidate windows are generated strictly within individual episodes. High-value hooks that span across the end of Episode N and the beginning of Episode N+1 are not captured. Cross-episode window stitching would address this.

3. Rule-Based Pre-Filtering vs End-to-End LLM:
   I intentionally chose deterministic regex parsing and duration bounding over prompting the LLM with raw, unsegmented episode text. This guarantees mathematically correct timecodes, prevents hallucinations, and achieves a measured 28% character reduction per episode while discarding non-dialogue boilerplate. A post-filter in `run.py` strictly prevents any LLM sub-window from violating the 20.0s duration minimum.

## Production Funnel Economics

In microdrama performance marketing (TikTok, Instagram Reels, YouTube Shorts), media buyers launch top-performing, high-converting hooks rather than 50 mediocre ads.

The pipeline implements an intentional two-stage evaluation funnel:
1. Stage 1 (Deterministic Parser): Parses 100% of the 50 episodes, generating structured scene cues and filtering out non-contiguous or un-scorable dialogue blocks into 565 candidate windows.
2. Stage 2 (Evaluator & Global Ranker): Candidate windows are scored and ranked down to top non-overlapping viral cuts. In the assignment prototype, this is bounded to respect free-tier API quotas ($0.00 cost, zero API calls via the on-device engine). In production, a paid batch API (~$0.13 per show on Gemini 3.8 Flash) evaluates all 565 candidate windows exhaustively.

## AI Tools Used and Development Experience

- **Tools Employed:** Claude Sonnet 4.6 (Thinking) for architecture reasoning, the regex parser and the UI. Gemini 3.8 Flash as the primary scorer and for the 60-window cross-check.
- **Where the AI Got It Wrong:** The LLM originally assumed screenplay scenes were uniformly segmented and advised slicing candidates purely along whole scene boundaries. However, Episode 8 contained an unsegmented 78-second continuous scene, causing the LLM to output zero viable 20–60s windows until we rejected the model's design and engineered sub-scene event-level sliding windows in deterministic Python code.
