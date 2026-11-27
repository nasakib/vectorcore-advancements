# ClothOS & Loom Fabric: Plain-English Master Guide

This document explains everything we built, fixed, and cleaned up in plain language—without heavy technical jargon.

---

## 1. The Main Problem We Solved: Why the System Was Repeating Itself

Previously, two parts of the system suffered from **short-term memory loss**:

1. **Long AI conversations forgot the plot**: When conversations or autonomous writing loops grew long, a trimming step deleted older messages to save space. Once old chapters were deleted, the AI forgot what had already happened and started repeating the same handful of phrases over and over.
2. **24/7 art and reports got stuck in a loop**:
   - A counter that numbered new creations (`lMinted Dream #...`) only looked at the last 60 items in a list, so once the list hit 60, every new piece became `#61` forever.
   - Short 15-second timeouts caused the AI to time out and fall back to the same 5 pre-written templates (for example, the same poem or story title).
   - Every time a report or gallery opened, it could write duplicate files to disk, piling up over **135,000** mostly identical files.

### How We Fixed It
- **Rolling Story Memory** ([unified_nexus.py](loom/unified_nexus.py)): Instead of throwing away older messages when trimming history, the system now writes a compact summary of what happened so far and keeps passing that summary forward.
- **Plan First, Check Uniqueness, Then Create** ([deliberation_engine.py](loom/clothos/deliberation_engine.py)):
  - Before making any art, story, music, video, or report, the system reads a permanent log (`data/deliberation_trajectory.json`) of what it has already made.
  - It plans a fresh idea, checks that the title, structure, and text are not too similar to past work, and only then generates the final piece.
  - The numbering counter now increases permanently (`1, 2, 3, ...`) and never resets to `#61`.
  - Quality comes before speed: models are given generous time to think instead of failing after 15 seconds into canned templates.

---

## 2. Real Multimedia Generation (Images, Video, Music, Stories)

Previously, "visual art" and "video" were mostly simple SVG shapes or browser-only animations, and "music" was a short basic drone. Now the system creates real, playable media files ([multimodal_synth.py](loom/clothos/multimodal_synth.py), [creative_art.py](loom/clothos/creative_art.py)):

- **Images** (`.png`, `.webp`, and `.svg`): Uses 7 different mathematical visual engines (chemical reaction-diffusion patterns, chaotic attractors, standing wave plates, fluid noise fields, fractals, spirals, and 200-region network maps) to draw unique high-resolution images.
- **Music** (`.wav`, `.flac`, `.mid`, plus a web player): Composes multi-part stereo music across 7 musical scales with chord progressions, melodies, bass, drum pulses, reverb, and slow breathing volume curves.
- **Video** (`.avi`, `.webp`, `.gif`, plus an interactive web canvas): Renders frame-by-frame animations into real playable `.avi` video files that include a synchronized stereo soundtrack, alongside looping `.webp` and `.gif` files.
- **Stories & Poetry**: Generates original narratives and structured poems checked against the uniqueness log so old stories aren't recycled.

### Prompting What You Want Directly
You can tell ClothOS what to make in plain English ([creative_art.py](loom/clothos/creative_art.py), [agent_cli.py](loom/clothos/agent_cli.py)):
- **In the command-line tool (`clothos-agent.bat`)**:
  - Type naturally: `"make me a glowing Lorenz attractor video"`, `"create an image of coral patterns"`, or `"compose a dorian synth track"`.
  - Or use shortcuts: `/video <prompt>`, `/image <prompt>`, `/music <prompt>`, `/story <prompt>`, `/poem <prompt>`, `/media <prompt>` (auto-picks the right format), or `/multimedia <prompt>` (creates an image, video, music track, and story together).
- **In the Web Dashboard (`http://localhost:8087`)**:
  - Go to **The Atelier** tab -> **Prompt Multimedia Generation Studio**.
  - Leave it on **Auto-Detect from Prompt** (or pick a specific format), type what you want, and press **Enter** or click **Generate**. Images, audio players, video previews, and download links appear right on the page.

---

## 3. Reading & Analyzing Any File Type

Previously, if you fed a non-text file (like an image, audio track, video, database, or notebook) into the document reader, it tried to read raw binary bytes as plain text and produced garbled output.

Now, [universal_file_analyzer.py](loom/clothos/universal_file_analyzer.py) (and [doc_parser.py](loom/clothos/doc_parser.py)) inspects the actual file header and format to extract useful information from **any** file type:
- **Documents & Notebooks**: PDF, Word (`.docx`), PowerPoint (`.pptx`), Excel/CSV, HTML, Markdown, and Jupyter Notebooks (`.ipynb`, reading each markdown and code cell cleanly).
- **Code & Data**: Python files (lists classes and functions), JSON, YAML, TOML, NumPy arrays (`.npy`/`.npz`), and SQLite databases (lists tables, columns, row counts, and sample rows).
- **Images**: Dimensions, camera/EXIF info, brightness, edge sharpness, and top 5 colors.
- **Audio & MIDI**: Length, sample rate, stereo/mono, loudness, and dominant musical frequencies.
- **Video**: Resolution, frame rate (FPS), duration, codecs, and motion between frames (`.avi`, `.mp4`/`.mov`, `.mkv`/`.webm`, animated `.gif`/`.webp`).
- **3D Models & Science Files**: 3D print meshes (`.stl`, `.step`, `.obj`) and protein/molecular structures (`.cif`, `.pdb`).
- **Archives & Unknown Files**: Lists files inside `.zip`/`.tar` archives, or safely reports file signature, fingerprint (SHA-256), randomness score, and readable text strings for raw binaries.

**Where to use it**: Upload any file in **The Atelier -> Universal File Analyzer** on the Web Dashboard (`http://localhost:8087`), or ask the CLI agent to inspect a file (`analyze_file`).

---

## 4. Cleaning Up the 135,000+ File Backlog

To clear out years/days of repetitive cycle spam without losing unique work, we built a workspace organizer ([work_consolidator.py](loom/clothos/work_consolidator.py)) and ran it across the project:
- **Scanned**: `135,055` files across `deliverables/` and `artifacts/`.
- **Collapsed duplicates**: Found `1,756` distinct creations across reports, stories, poetry, music, videos, images, and 3D/CAD models.
- **Kept active**: Preserved the `25` newest unique pieces in each category (`175` files) plus main live reports (`LATEST_24X7_REPORT.md` and `LATEST_24X7_DISCOVERIES.json`).
- **Archived & cleaned**: Bundled historical works into compressed `.zip` files and wrote a master index (`deliverables/archives/consolidated/CONSOLIDATED_CATALOG.json` and `CONSOLIDATED_SYNTHESIS.md`), removing `134,880` duplicate/stale loose files.

---

## 5. Self-Training With Llama 70B & Truth Checking

1. **70B Teacher Training** ([distillation_trainer.py](loom/models/distillation_trainer.py), [self_training_knowledge_engine.py](loom/clothos/self_training_knowledge_engine.py)):
   - Fixed a bug where each training cycle wiped and overwrote the training file (`loom_70b_distillation_pairs.jsonl`) with 5 static examples. It now **appends** only new, deduplicated examples and compiles a readable summary (`data/training/loom_sovereign_distilled_lessons.md`).
   - Increased the teacher timeout from 30s to 240s and added a memory check so the 42 GB `llama3.3:70b` model can finish critiquing and teaching smaller models (`loom-sovereign`, `loom-fabric`) without crashing or starving your interactive sessions.
2. **Truth & Quality Guardrails** ([simplex_substrate.py](loom/clothos/simplex_substrate.py)):
   - Added automatic checks that catch repetitive/collapsed text before saving reports (`deliverable_synthesizer.py`), pack data cleanly for current CPUs/GPUs and future hardware, and support local AES-256-GCM encryption for private session notes.
   - Added a `200x200` network-map visual and slow-wave (`0.030–0.039 Hz`) rhythmic pacing into the image and music generators.

---

## 6. Fixing Live AI Coherence & Unifying the Brand

- **Live AI Connection**: Ollama was not running on your machine (`11434`), which caused `clothos-agent.bat` to fail through every fallback model. We started the Ollama server and confirmed your installed models are ready (`loom-sovereign-fast:latest` 7B, `loom-sovereign:latest` 32B based on `qwen2.5:32b`, `loom-70b:latest` / `llama3.3:70b` 70B, and `qwen2.5-coder:7b`).
- **CLI Shortcuts**: Added `/models` (as a shortcut for `/model list`) so checking/switching models works cleanly.
- **Unified Brand**: Replaced old `Apostrophie` naming across 31 source files, docs, scripts, and tests so everything consistently uses **ClothOS**.

---

## 7. Quick Cheat Sheet: How to Use Everything Day-to-Day

1. **Start the background services** (in `c:\Users\natsa\Documents\loom-fabric`):
   - **Web Dashboard**: `.venv\Scripts\python.exe -m uvicorn loom.fabric.dashboard_server:app --host 0.0.0.0 --port 8087` -> open `http://localhost:8087`
   - **24/7 Autonomous Loop**: run `Start-24-7-Compute.bat`
2. **Talk to ClothOS in the Terminal**:
   - Run `.\clothos-agent.bat`
   - Switch model anytime: `/models` to list, `/model use loom-sovereign` (32B), `/model use loom-sovereign-70b` (70B), or `/model use loom-sovereign-fast` (fast 7B).
   - Generate media: type `/video ...`, `/image ...`, `/music ...`, `/story ...`, or ask in plain English.
3. **Where Your Outputs Live**:
   - **Media files** (PNG, AVI, GIF, WebP, WAV, FLAC, MIDI): `artifacts/art/`
   - **Latest 24/7 summary & discoveries**: `deliverables/LATEST_24X7_REPORT.md` and `deliverables/LATEST_24X7_DISCOVERIES.json`
   - **Consolidated archives**: `deliverables/archives/consolidated/`
   - **70B training log & lessons**: `data/training/loom_70b_distillation_pairs.jsonl` and `data/training/loom_sovereign_distilled_lessons.md`
