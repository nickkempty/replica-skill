# Highlight Shorts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local web app that takes a permitted YouTube video, picks gameplay highlights by itself, and turns them into vertical Shorts with the owner's own voiceover, burned-in subtitles and a private upload to their channel.

**Architecture:** A Python package `hshorts` with one module per responsibility (ingest, analyze, highlights, render, subtitles, upload), a JSON-file project store, and a FastAPI server that runs heavy work on a background thread and serves a no-build HTML/JS page. ffmpeg does all media work; numpy does the scoring.

**Tech Stack:** Python 3.10+, FastAPI, uvicorn, numpy, ffmpeg/ffprobe, yt-dlp, faster-whisper, google-api-python-client, google-auth-oauthlib, pytest.

**Spec:** `docs/superpowers/specs/2026-11-15-highlight-shorts-design.md`

## Global Constraints

- All code lives in `highlight-shorts/`. No `SKILL.md` in it. The repo's own 57 tests must stay green.
- No em dash character in any `.md`, `.py`, `.json` file (repo test enforces it).
- Runs fully on the user's machine. No AI API key. No database.
- Output clips are 1080x1920, H.264 + AAC, at most 60 seconds.
- yt-dlp, faster-whisper and the Google libraries are imported lazily inside the functions that use them, so tests run without them.
- Uploads are always `privacyStatus: private`, and refused unless the clip has a voiceover.
- A project cannot be created unless `permission` is true and a source channel name is given.
- Project data lives outside the repo: `$HS_DATA` or `~/highlight-shorts-data`.
- User-facing text in the web page is Thai.

## Review Focus

1. Source video with no audio track: analysis must still work, using motion only.
2. Source shorter than the minimum clip length: return one clip covering the whole video.
3. Flat signal (silent, static video): no divide by zero, still returns clips.
4. Thai text, quotes, colons, backslashes and braces in subtitles and file paths: the ASS file and the ffmpeg filter string must survive them.
5. Download or analysis failure: the project shows stage `error` with the message, the server keeps running.

---

## File map

| File | Responsibility |
| --- | --- |
| `highlight-shorts/hshorts/media.py` | `run`, `probe`, `ensure_mp4` |
| `highlight-shorts/hshorts/analyze.py` | per-second loudness, motion, speech signals and the combined score |
| `highlight-shorts/hshorts/highlights.py` | peak picking, windows, reasons |
| `highlight-shorts/hshorts/subtitles.py` | Whisper transcription, ASS writer |
| `highlight-shorts/hshorts/render.py` | ffmpeg command builder and clip render |
| `highlight-shorts/hshorts/store.py` | project JSON store |
| `highlight-shorts/hshorts/ingest.py` | yt-dlp download, local file import |
| `highlight-shorts/hshorts/upload.py` | OAuth, private upload, description builder |
| `highlight-shorts/hshorts/pipeline.py` | job thread: ingest, analyze, pick; voice; render |
| `highlight-shorts/hshorts/server.py` | FastAPI routes |
| `highlight-shorts/hshorts/web/` | `index.html`, `app.js`, `style.css` |
| `highlight-shorts/tests/` | pytest suite, synthetic video fixture in `conftest.py` |
| `highlight-shorts/README.md`, `requirements.txt` | Thai setup guide, dependencies |

### Task 1: Media helpers, analysis, highlight picking

**Produces:**
- `media.probe(path) -> {"duration": float, "width": int, "height": int, "has_audio": bool, "vcodec": str}`
- `analyze.loudness(path, duration) -> np.ndarray` (dB per second; zeros if no audio)
- `analyze.motion(path, duration) -> np.ndarray` (mean abs frame difference per second, 32x18 gray, 2 fps)
- `analyze.speech(segments, duration) -> np.ndarray` (words per second, +2 per `!` or `?`)
- `analyze.score(loud, motion, speech=None) -> (scores, parts)`; `parts` is a dict of normalised arrays keyed `loud`, `onset`, `motion`, `speech`. Weights 0.4, 0.2, 0.3, 0.1, renormalised over signals that vary. Robust z-score (median, MAD, fall back to std, then zeros). 5 second moving average.
- `highlights.pick(scores, parts, loud, duration, count=8, min_len=20, max_len=45, exclude=()) -> list[dict]` with keys `start`, `end`, `score`, `reason`. Greedy on peaks, grow window while neighbours stay above the median score, snap each edge to the quietest second within 3 seconds, no overlap with chosen or excluded windows, sorted by score descending.

- [ ] Tests: synthetic 60 s video with a loud burst and fast motion at 30 to 40 s is picked first; no-audio video; 8 s video returns one clip `0..8`; all-zero signals; windows never overlap, lengths within bounds; `exclude` respected.
- [ ] Implement, run `pytest highlight-shorts/tests -q`, commit.

### Task 2: Subtitles and render

**Produces:**
- `subtitles.transcribe(audio_path, language=None, model="small") -> list[{"start","end","text"}]`
- `subtitles.write_ass(subs, path, font=None) -> None` (PlayRes 1080x1920, bottom centre, margin 260, size 72, outline 4)
- `render.build_cmd(src, out, start, end, crop_mode="crop", crop_x=0.5, voice=None, duck=0.2, ass=None, has_audio=True) -> list[str]`
- `render.render_clip(...same args...) -> str`

- [ ] Tests: rendered clip probes as 1080x1920 with audio and the requested duration, in both `crop` and `blur` modes; with voice and Thai subtitles containing `{`, `\`, `:` and `'`; from a source with no audio; `end - start` above 60 raises `ValueError`.
- [ ] Implement, run, commit.

### Task 3: Store, ingest, upload helpers, pipeline

**Produces:**
- `store.create(url, file_path, channel, permission, settings) -> project` (raises `ValueError` without permission or channel, or with a non-http URL), `store.load`, `store.save`, `store.all`, `store.pdir`
- `ingest.download(url, dest_dir, on_progress) -> (path, title)`, `ingest.import_file(path, dest_dir) -> (path, title)`
- `upload.describe(text, channel, url) -> str`, `upload.connected() -> bool`, `upload.connect() -> None`, `upload.send(path, title, description, tags) -> video_id`
- `pipeline.start(fn, *args)`, `pipeline.process(pid)`, `pipeline.add_more(pid, n)`, `pipeline.set_voice(pid, cid, raw_bytes)`, `pipeline.render(pid, cid)`

- [ ] Tests: permission rules; `process` on a local file ends at stage `ready` with clips; a missing file ends at stage `error`; `describe` includes the credit and link; `upload.send` builds a body with `private` (Google client mocked).
- [ ] Implement, run, commit.

### Task 4: Server and web page

**Produces:** routes under `/api` for projects, clips, voice, render, upload, YouTube status; the Thai single-page UI with the six steps from the spec.

- [ ] Tests (FastAPI TestClient): create needs permission (400); full flow create, poll to `ready`, patch a clip, post a voice recording, render, download file; upload without voice returns 409; clip edits longer than 60 s return 400.
- [ ] Implement, run, drive the page once in Chromium with a synthetic video, commit.

### Task 5: README and final check

- [ ] Thai README: install, run, Google OAuth setup step by step, limits (private uploads, about 6 a day), permission reminder.
- [ ] Run both test suites, push.
