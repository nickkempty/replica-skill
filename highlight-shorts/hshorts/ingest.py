"""Get the source video into the project folder as a browser-playable mp4."""
import os

from . import media


def download(url, dest_dir, on_progress=None):
    """Download with yt-dlp. Returns (path, title)."""
    import yt_dlp

    def hook(d):
        if on_progress and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if total:
                on_progress(d.get("downloaded_bytes", 0) / total)

    opts = {
        "format": "bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/b[height<=1080]/b",
        "merge_output_format": "mp4", "noplaylist": True, "quiet": True, "no_warnings": True,
        "outtmpl": os.path.join(dest_dir, "download.%(ext)s"), "progress_hooks": [hook],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        got = ydl.prepare_filename(info)
    if not os.path.isfile(got):
        got = os.path.splitext(got)[0] + ".mp4"
    return _finish(got, dest_dir), info.get("title") or "video"


def import_file(path, dest_dir):
    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        raise FileNotFoundError("ไม่พบไฟล์: %s" % path)
    title = os.path.splitext(os.path.basename(path))[0]
    return _finish(path, dest_dir), title


def _finish(path, dest_dir):
    out = os.path.join(dest_dir, "source.mp4")
    media.ensure_mp4(path, out)
    if os.path.dirname(os.path.abspath(path)) == os.path.abspath(dest_dir):
        os.remove(path)
    return out
