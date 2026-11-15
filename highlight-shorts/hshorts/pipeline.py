"""The slow work: ingest, analyse, pick, voice, render. Runs on background threads."""
import os
import threading
import traceback

import numpy as np

from . import analyze, highlights, ingest, media, render, store, subtitles


def start(fn, *args):
    thread = threading.Thread(target=fn, args=args, daemon=True)
    thread.start()
    return thread


def _stage(pid, stage, progress=0, error=""):
    store.update(pid, lambda p: p["status"].update(stage=stage, progress=progress, error=error))


def _new_clip(project, found):
    number = project["next_clip"]
    project["next_clip"] += 1
    base = project["title"] or "Shorts"
    return {
        "id": "c%d" % number, "start": found["start"], "end": found["end"],
        "score": found["score"], "reason": found["reason"],
        "crop_mode": "crop", "crop_x": 0.5, "duck": 0.2,
        "has_voice": False, "subtitles": [], "subtitle_note": "",
        "title": ("%s #%d #Shorts" % (base[:80], number)), "description": "",
        "tags": ["shorts"], "rendered": False, "busy": "", "error": "", "youtube_id": "",
    }


def _pick(pid, count):
    folder = store.pdir(pid)
    data = np.load(os.path.join(folder, "signals.npz"))
    parts = {k[2:]: data[k] for k in data.files if k.startswith("p_")}

    def apply(project):
        s = project["settings"]
        found = highlights.pick(data["scores"], parts, data["loud"], project["duration"],
                                count=count, min_len=s["min_len"], max_len=s["max_len"],
                                exclude=[(c["start"], c["end"]) for c in project["clips"]])
        project["clips"].extend(_new_clip(project, f) for f in found)
        project["last_added"] = len(found)
    return store.update(pid, apply)


def process(pid):
    """Download or import, analyse, and choose the highlights."""
    try:
        project = store.load(pid)
        folder = store.pdir(pid)
        _stage(pid, "downloading")
        if project["source_url"]:
            path, title = ingest.download(
                project["source_url"], folder,
                lambda f: _stage(pid, "downloading", round(f * 100)))
        else:
            path, title = ingest.import_file(project["source_file"], folder)
        info = media.probe(path)
        store.update(pid, lambda p: p.update(title=title, duration=info["duration"],
                                             has_audio=info["has_audio"]))
        _stage(pid, "analyzing", 10)
        loud = analyze.loudness(path, info["duration"])
        _stage(pid, "analyzing", 40)
        mot = analyze.motion(path, info["duration"])
        spe = None
        if project["settings"]["use_speech"] and info["has_audio"]:
            _stage(pid, "analyzing", 60)
            spe = analyze.speech(subtitles.transcribe(path), info["duration"])
        scores, parts = analyze.score(loud, mot, spe)
        np.savez(os.path.join(folder, "signals.npz"), scores=scores, loud=loud,
                 **{"p_" + k: v for k, v in parts.items()})
        _stage(pid, "picking", 90)
        _pick(pid, project["settings"]["count"])
        _stage(pid, "ready", 100)
    except Exception as exc:  # the server must outlive a failed job
        traceback.print_exc()
        _stage(pid, "error", 0, str(exc) or exc.__class__.__name__)


def add_more(pid, count=4):
    return _pick(pid, count)


def _clip_paths(pid, cid):
    folder = store.pdir(pid)
    return {k: os.path.join(folder, "%s.%s" % (cid, ext))
            for k, ext in (("voice", "wav"), ("ass", "ass"), ("out", "mp4"))}


def _set(pid, cid, **fields):
    store.update(pid, lambda p: store.clip(p, cid).update(**fields))


def set_voice(pid, cid, raw):
    """Store a browser recording as wav, then try to make subtitles from it."""
    paths = _clip_paths(pid, cid)
    upload = paths["voice"] + ".upload"
    with open(upload, "wb") as fh:
        fh.write(raw)
    try:
        media.run(["ffmpeg", "-y", "-v", "error", "-i", upload, "-vn", "-ac", "1",
                   "-ar", "44100", paths["voice"]])
    finally:
        os.remove(upload)
    _set(pid, cid, has_voice=True, rendered=False, busy="subtitles", error="", youtube_id="")
    start(_subtitle, pid, cid)


def _subtitle(pid, cid):
    try:
        subs = subtitles.transcribe(_clip_paths(pid, cid)["voice"])
        _set(pid, cid, subtitles=subs, subtitle_note="", busy="")
    except Exception as exc:
        note = "ถอดเสียงอัตโนมัติไม่สำเร็จ (%s) พิมพ์ซับเองได้" % (str(exc) or exc.__class__.__name__)
        _set(pid, cid, subtitle_note=note, busy="")


def render_job(pid, cid):
    try:
        project = store.load(pid)
        c = store.clip(project, cid)
        paths = _clip_paths(pid, cid)
        subs = [s for s in c["subtitles"] if s.get("text", "").strip()]
        if subs:
            subtitles.write_ass(subs, paths["ass"])
        render.render_clip(os.path.join(store.pdir(pid), "source.mp4"), paths["out"],
                           c["start"], c["end"], c["crop_mode"], c["crop_x"],
                           paths["voice"] if c["has_voice"] else None, c["duck"],
                           paths["ass"] if subs else None)
        _set(pid, cid, rendered=True, busy="", error="")
    except Exception as exc:
        traceback.print_exc()
        _set(pid, cid, rendered=False, busy="", error=str(exc) or exc.__class__.__name__)


def upload_job(pid, cid):
    from . import upload
    try:
        project = store.load(pid)
        c = store.clip(project, cid)
        vid = upload.send(_clip_paths(pid, cid)["out"], c["title"],
                          upload.describe(c["description"], project["channel"],
                                          project["source_url"]), c["tags"])
        _set(pid, cid, youtube_id=vid, busy="", error="")
    except Exception as exc:
        traceback.print_exc()
        _set(pid, cid, busy="", error=str(exc) or exc.__class__.__name__)
