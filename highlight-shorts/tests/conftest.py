import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_video(path, seconds=60, burst=(30, 40), audio=True):
    """Calm gray video with quiet tone; noisy picture and loud noise inside `burst`."""
    a, b = burst
    gate = "between(t,%d,%d)" % (a, b)
    vf = ("[0:v]noise=alls=100:allf=t:enable='%s',format=yuv420p[v]" % gate)
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-f", "lavfi", "-i", "color=c=gray:s=320x180:r=10:d=%d" % seconds]
    if audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=220:duration=%d" % seconds,
                "-f", "lavfi", "-i", "anoisesrc=d=%d:c=white" % seconds]
        af = ("[1:a]volume=0.02[q];[2:a]volume='if(%s,0.9,0)':eval=frame[n];"
              "[q][n]amix=inputs=2:normalize=0[a]" % gate)
        cmd += ["-filter_complex", vf + ";" + af, "-map", "[v]", "-map", "[a]",
                "-c:a", "aac"]
    else:
        cmd += ["-filter_complex", vf, "-map", "[v]"]
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-t", str(seconds), path]
    subprocess.run(cmd, check=True)
    return path


@pytest.fixture(scope="session")
def video(tmp_path_factory):
    return make_video(str(tmp_path_factory.mktemp("v") / "game.mp4"))


@pytest.fixture(scope="session")
def silent_video(tmp_path_factory):
    return make_video(str(tmp_path_factory.mktemp("v") / "silent.mp4"), audio=False)


@pytest.fixture(scope="session")
def short_video(tmp_path_factory):
    return make_video(str(tmp_path_factory.mktemp("v") / "short.mp4"), seconds=8, burst=(2, 4))


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("HS_DATA", str(tmp_path / "data"))
    return str(tmp_path / "data")
