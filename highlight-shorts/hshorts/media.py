"""Thin wrappers around ffmpeg and ffprobe."""
import json
import os
import subprocess


class MediaError(RuntimeError):
    pass


def run(cmd, binary=False, cwd=None):
    """Run a command, return stdout. Raise MediaError with the tail of stderr."""
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", "replace").strip().splitlines()[-6:]
        raise MediaError("%s failed: %s" % (cmd[0], " | ".join(tail)))
    return proc.stdout if binary else proc.stdout.decode("utf-8", "replace")


def probe(path):
    if not os.path.isfile(path):
        raise MediaError("file not found: %s" % path)
    out = run(["ffprobe", "-v", "error", "-print_format", "json",
               "-show_format", "-show_streams", path])
    info = json.loads(out)
    video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if video is None:
        raise MediaError("no video stream in %s" % path)
    audio = any(s.get("codec_type") == "audio" for s in info["streams"])
    duration = float(info.get("format", {}).get("duration") or video.get("duration") or 0)
    return {"duration": duration, "width": int(video["width"]), "height": int(video["height"]),
            "has_audio": audio, "vcodec": video.get("codec_name", "")}


def ensure_mp4(path, dest):
    """Give back an H.264 mp4 a browser can play. Copy streams when possible."""
    info = probe(path)
    if info["vcodec"] == "h264":
        video = ["-c:v", "copy"]
    else:
        video = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
    run(["ffmpeg", "-y", "-v", "error", "-i", path, "-map", "0:v:0", "-map", "0:a:0?"]
        + video + ["-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", dest])
    return dest
