"""Projects are folders with a project.json. No database."""
import json
import os
import re
import threading
import time
import uuid

LOCK = threading.RLock()
DEFAULTS = {"count": 8, "min_len": 20, "max_len": 45, "use_speech": False}


def data_dir():
    path = os.environ.get("HS_DATA") or os.path.join(os.path.expanduser("~"),
                                                     "highlight-shorts-data")
    os.makedirs(os.path.join(path, "projects"), exist_ok=True)
    return path


def pdir(pid):
    if not re.fullmatch(r"[0-9a-f]{12}", pid or ""):
        raise KeyError(pid)
    return os.path.join(data_dir(), "projects", pid)


def clean_settings(settings):
    out = dict(DEFAULTS)
    for key in ("count", "min_len", "max_len"):
        if (settings or {}).get(key) is not None:
            out[key] = int(settings[key])
    out["use_speech"] = bool((settings or {}).get("use_speech", False))
    out["count"] = min(30, max(1, out["count"]))
    out["max_len"] = min(60, max(5, out["max_len"]))
    out["min_len"] = min(out["max_len"], max(5, out["min_len"]))
    return out


def create(url, file_path, channel, permission, settings=None):
    url, file_path, channel = (url or "").strip(), (file_path or "").strip(), (channel or "").strip()
    if permission is not True:
        raise ValueError("ต้องยืนยันว่าได้รับอนุญาตจากเจ้าของวิดีโอก่อน")
    if not channel:
        raise ValueError("กรุณากรอกชื่อช่องหรือเจ้าของวิดีโอต้นทาง เพื่อใช้เป็นเครดิต")
    if bool(url) == bool(file_path):
        raise ValueError("ใส่ลิงก์ หรือ ที่อยู่ไฟล์ในเครื่อง อย่างใดอย่างหนึ่ง")
    if url and not re.match(r"https?://", url):
        raise ValueError("ลิงก์ต้องขึ้นต้นด้วย http:// หรือ https://")
    project = {
        "id": uuid.uuid4().hex[:12], "created": time.time(), "title": "",
        "source_url": url, "source_file": file_path, "channel": channel,
        "permission_confirmed": True, "settings": clean_settings(settings),
        "status": {"stage": "queued", "progress": 0, "error": ""},
        "duration": 0, "clips": [], "next_clip": 1,
    }
    os.makedirs(pdir(project["id"]))
    save(project)
    return project


def save(project):
    with LOCK:
        path = os.path.join(pdir(project["id"]), "project.json")
        tmp = path + ".part"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(project, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, path)


def load(pid):
    with LOCK:
        try:
            with open(os.path.join(pdir(pid), "project.json"), encoding="utf-8") as fh:
                return json.load(fh)
        except FileNotFoundError:
            raise KeyError(pid)


def update(pid, fn):
    """Load, change, save under one lock, so the job thread and the server do not clash."""
    with LOCK:
        project = load(pid)
        fn(project)
        save(project)
        return project


def all():
    root = os.path.join(data_dir(), "projects")
    out = []
    for name in os.listdir(root):
        try:
            out.append(load(name))
        except KeyError:
            pass
    return sorted(out, key=lambda p: -p["created"])


def clip(project, cid):
    for c in project["clips"]:
        if c["id"] == cid:
            return c
    raise KeyError(cid)
