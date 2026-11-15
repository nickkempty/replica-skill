"""Local web server. Start with:  python -m hshorts"""
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import pipeline, render, store, upload

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
app = FastAPI(title="Highlight Shorts")
EDITABLE = ("start", "end", "crop_mode", "crop_x", "duck", "subtitles", "title",
            "description", "tags")
RERENDER = ("start", "end", "crop_mode", "crop_x", "duck", "subtitles")


def _project(pid):
    try:
        return store.load(pid)
    except KeyError:
        raise HTTPException(404, "ไม่พบงานนี้")


def _clip(project, cid):
    try:
        return store.clip(project, cid)
    except KeyError:
        raise HTTPException(404, "ไม่พบคลิปนี้")


def _file(pid, name):
    path = os.path.join(store.pdir(pid), name)
    if not os.path.isfile(path):
        raise HTTPException(404, "ยังไม่มีไฟล์นี้")
    return path


@app.get("/api/projects")
def projects():
    return [{k: p[k] for k in ("id", "title", "channel", "status", "created")}
            | {"clips": len(p["clips"])} for p in store.all()]


@app.post("/api/projects")
async def create(request: Request):
    data = await request.json()
    try:
        project = store.create(data.get("url"), data.get("file_path"), data.get("channel"),
                               data.get("permission"), data.get("settings"))
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc))
    pipeline.start(pipeline.process, project["id"])
    return project


@app.get("/api/projects/{pid}")
def project(pid: str):
    return _project(pid)


@app.get("/api/projects/{pid}/video")
def video(pid: str):
    _project(pid)
    return FileResponse(_file(pid, "source.mp4"), media_type="video/mp4")


@app.post("/api/projects/{pid}/more")
def more(pid: str):
    if _project(pid)["status"]["stage"] != "ready":
        raise HTTPException(409, "งานนี้ยังประมวลผลไม่เสร็จ")
    return pipeline.add_more(pid, 4)


@app.patch("/api/projects/{pid}/clips/{cid}")
async def edit(pid: str, cid: str, request: Request):
    data = await request.json()
    project = _project(pid)
    clip = dict(_clip(project, cid))
    changes = {k: data[k] for k in EDITABLE if k in data}
    try:
        clip.update(changes)
        clip["start"], clip["end"] = float(clip["start"]), float(clip["end"])
        clip["crop_x"], clip["duck"] = float(clip["crop_x"]), float(clip["duck"])
        if clip["crop_mode"] not in ("crop", "blur"):
            raise ValueError("crop_mode ต้องเป็น crop หรือ blur")
        if clip["start"] < 0 or clip["end"] > project["duration"] + 0.5:
            raise ValueError("ช่วงเวลาอยู่นอกวิดีโอ")
        if not 0 <= clip["crop_x"] <= 1 or not 0 <= clip["duck"] <= 1:
            raise ValueError("ค่าตำแหน่งภาพและความดังต้องอยู่ระหว่าง 0 ถึง 1")
        render.build_cmd("a", "b", clip["start"], clip["end"])
        clip["subtitles"] = [{"start": float(s["start"]), "end": float(s["end"]),
                              "text": str(s["text"])} for s in clip["subtitles"]]
        clip["tags"] = [str(t).strip() for t in clip["tags"] if str(t).strip()]
        clip["title"], clip["description"] = str(clip["title"]), str(clip["description"])
    except (ValueError, TypeError, KeyError) as exc:
        msg = str(exc)
        if "at most" in msg:
            msg = "คลิป Shorts ยาวได้ไม่เกิน 60 วินาที"
        elif "after its start" in msg:
            msg = "จุดจบต้องอยู่หลังจุดเริ่ม"
        raise HTTPException(400, msg or "ข้อมูลไม่ถูกต้อง")
    old = _clip(project, cid)
    if any(clip[k] != old[k] for k in RERENDER):
        clip["rendered"], clip["youtube_id"] = False, ""
    if (clip["start"], clip["end"]) != (old["start"], old["end"]) and old["has_voice"]:
        clip["voice_stale"] = True
    return store.clip(store.update(pid, lambda p: store.clip(p, cid).update(clip)), cid)


@app.delete("/api/projects/{pid}/clips/{cid}")
def remove(pid: str, cid: str):
    _clip(_project(pid), cid)
    store.update(pid, lambda p: p.update(clips=[c for c in p["clips"] if c["id"] != cid]))
    for ext in ("wav", "ass", "mp4"):
        path = os.path.join(store.pdir(pid), "%s.%s" % (cid, ext))
        if os.path.isfile(path):
            os.remove(path)
    return {"ok": True}


@app.post("/api/projects/{pid}/clips/{cid}/voice")
async def voice(pid: str, cid: str, request: Request):
    _clip(_project(pid), cid)
    raw = await request.body()
    if len(raw) < 200:
        raise HTTPException(400, "ไม่ได้รับเสียงที่อัด")
    try:
        pipeline.set_voice(pid, cid, raw)
    except Exception as exc:
        raise HTTPException(400, "อ่านไฟล์เสียงไม่ได้: %s" % exc)
    store.update(pid, lambda p: store.clip(p, cid).pop("voice_stale", None))
    return _clip(_project(pid), cid)


@app.get("/api/projects/{pid}/clips/{cid}/voice")
def voice_file(pid: str, cid: str):
    _clip(_project(pid), cid)
    return FileResponse(_file(pid, cid + ".wav"), media_type="audio/wav")


@app.post("/api/projects/{pid}/clips/{cid}/render")
def render_clip(pid: str, cid: str):
    clip = _clip(_project(pid), cid)
    if clip["busy"]:
        raise HTTPException(409, "คลิปนี้กำลังทำงานอยู่")
    store.update(pid, lambda p: store.clip(p, cid).update(busy="render", error=""))
    pipeline.start(pipeline.render_job, pid, cid)
    return {"ok": True}


@app.get("/api/projects/{pid}/clips/{cid}/file")
def clip_file(pid: str, cid: str, download: int = 0):
    clip = _clip(_project(pid), cid)
    if not clip["rendered"]:
        raise HTTPException(404, "คลิปนี้ยังไม่ได้ส่งออก")
    name = "%s-%s.mp4" % (pid, cid) if download else None
    return FileResponse(_file(pid, cid + ".mp4"), media_type="video/mp4", filename=name)


@app.post("/api/projects/{pid}/clips/{cid}/upload")
def upload_clip(pid: str, cid: str):
    clip = _clip(_project(pid), cid)
    if not clip["has_voice"] or clip.get("voice_stale"):
        raise HTTPException(409, "ต้องพากเสียงของคุณทับคลิปนี้ก่อนจึงจะอัปได้")
    if not clip["rendered"]:
        raise HTTPException(409, "ต้องส่งออกคลิปก่อนอัป")
    if clip["busy"]:
        raise HTTPException(409, "คลิปนี้กำลังทำงานอยู่")
    if not upload.connected():
        raise HTTPException(409, "ยังไม่ได้เชื่อมบัญชี YouTube")
    store.update(pid, lambda p: store.clip(p, cid).update(busy="upload", error=""))
    pipeline.start(pipeline.upload_job, pid, cid)
    return {"ok": True}


@app.get("/api/youtube")
def youtube():
    return {"has_client": upload.has_client(), "connected": upload.connected(),
            "data_dir": store.data_dir()}


@app.post("/api/youtube/connect")
def youtube_connect():
    try:
        upload.connect()
    except Exception as exc:
        raise HTTPException(400, str(exc) or exc.__class__.__name__)
    return youtube()


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
