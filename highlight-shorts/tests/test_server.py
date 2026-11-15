import subprocess
import time

import pytest
from fastapi.testclient import TestClient

from hshorts import pipeline, server, upload


@pytest.fixture()
def client(data_dir, monkeypatch):
    def fake_transcribe(path, language=None, model="small"):
        return [{"start": 0.0, "end": 2.0, "text": "โคตรมันส์!"}]
    monkeypatch.setattr(pipeline.subtitles, "transcribe", fake_transcribe)
    return TestClient(server.app)


def wait(client, pid, test, seconds=60):
    end = time.time() + seconds
    while time.time() < end:
        p = client.get("/api/projects/" + pid).json()
        if test(p):
            return p
        time.sleep(0.2)
    raise AssertionError("timed out: %s" % p)


def new(client, video, **kw):
    body = {"file_path": video, "channel": "RockstarFan", "permission": True,
            "settings": {"count": 2, "min_len": 10, "max_len": 20}}
    body.update(kw)
    return client.post("/api/projects", json=body)


def recording(tmp_path):
    path = str(tmp_path / "rec.webm")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "sine=frequency=300:duration=3", "-c:a", "libopus", path], check=True)
    with open(path, "rb") as fh:
        return fh.read()


def test_create_needs_permission(client, video):
    r = new(client, video, permission=False)
    assert r.status_code == 400 and "อนุญาต" in r.json()["detail"]
    assert client.get("/api/projects").json() == []


def test_full_flow(client, video, tmp_path, monkeypatch):
    pid = new(client, video).json()["id"]
    p = wait(client, pid, lambda p: p["status"]["stage"] in ("ready", "error"))
    assert p["status"]["stage"] == "ready" and len(p["clips"]) == 2
    cid = p["clips"][0]["id"]
    base = "/api/projects/%s/clips/%s" % (pid, cid)

    assert client.get("/api/projects/%s/video" % pid, headers={"Range": "bytes=0-99"}).status_code == 206

    assert client.patch(base, json={"start": 0, "end": 61}).status_code == 400
    assert client.patch(base, json={"start": 9, "end": 5}).status_code == 400
    assert client.patch(base, json={"crop_mode": "zoom"}).status_code == 400
    assert client.patch(base, json={"end": 999}).status_code == 400
    r = client.patch(base, json={"start": 30, "end": 36, "crop_x": 0.7, "tags": ["gta6", " "]})
    assert r.status_code == 200 and r.json()["tags"] == ["gta6"]

    assert client.post(base + "/upload").status_code == 409
    assert client.post(base + "/voice", content=b"x").status_code == 400
    assert client.post(base + "/voice", content=b"x" * 500).status_code == 400

    assert client.post(base + "/voice", content=recording(tmp_path)).status_code == 200
    p = wait(client, pid, lambda p: p["clips"][0]["busy"] == "")
    assert p["clips"][0]["has_voice"] and p["clips"][0]["subtitles"][0]["text"] == "โคตรมันส์!"
    assert client.get(base + "/voice").status_code == 200

    assert client.get(base + "/file").status_code == 404
    assert client.post(base + "/upload").status_code == 409
    assert client.post(base + "/render").status_code == 200
    p = wait(client, pid, lambda p: p["clips"][0]["busy"] == "")
    assert p["clips"][0]["rendered"], p["clips"][0]["error"]
    assert client.get(base + "/file").headers["content-type"] == "video/mp4"

    assert client.post(base + "/upload").status_code == 409  # not connected
    sent = {}
    monkeypatch.setattr(upload, "connected", lambda: True)
    monkeypatch.setattr(upload, "send", lambda path, title, desc, tags: sent.update(
        path=path, desc=desc) or "yt123")
    assert client.post(base + "/upload").status_code == 200
    p = wait(client, pid, lambda p: p["clips"][0]["busy"] == "")
    assert p["clips"][0]["youtube_id"] == "yt123" and "RockstarFan" in sent["desc"]

    # moving the clip makes the old voiceover stale: no upload until it is redone
    assert client.patch(base, json={"start": 31, "end": 37}).json()["rendered"] is False
    assert client.post(base + "/upload").status_code == 409

    assert len(client.post("/api/projects/%s/more" % pid).json()["clips"]) >= 2
    assert client.delete(base).status_code == 200
    assert client.get(base + "/voice").status_code == 404


def test_failed_job_is_reported_and_server_survives(client):
    pid = new(client, "/nope/missing.mp4").json()["id"]
    p = wait(client, pid, lambda p: p["status"]["stage"] in ("ready", "error"))
    assert p["status"]["stage"] == "error" and p["status"]["error"]
    assert client.get("/api/projects").status_code == 200
    assert client.get("/api/projects/zzz").status_code == 404
    assert client.get("/api/youtube").json()["connected"] is False
