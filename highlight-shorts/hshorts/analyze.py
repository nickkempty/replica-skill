"""Turn a video into per-second signals and one highlight score per second."""
import math

import numpy as np

from . import media

RATE = 8000
W, H, FPS = 32, 18, 2
WEIGHTS = {"loud": 0.4, "onset": 0.2, "motion": 0.3, "speech": 0.1}


def _fit(values, seconds):
    out = np.zeros(seconds, dtype=float)
    n = min(seconds, len(values))
    out[:n] = values[:n]
    return out


def loudness(path, duration):
    """dB per second. All zeros when the file has no audio."""
    seconds = max(1, int(math.ceil(duration)))
    if not media.probe(path)["has_audio"]:
        return np.zeros(seconds)
    raw = media.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(RATE),
                     "-f", "s16le", "-"], binary=True)
    pcm = np.frombuffer(raw, dtype=np.int16).astype(float) / 32768.0
    n = len(pcm) // RATE
    if n == 0:
        return np.zeros(seconds)
    rms = np.sqrt((pcm[:n * RATE].reshape(n, RATE) ** 2).mean(axis=1))
    return _fit(20 * np.log10(np.maximum(rms, 1e-4)) + 80, seconds)


def motion(path, duration):
    """Mean absolute frame difference per second on a tiny grayscale copy."""
    seconds = max(1, int(math.ceil(duration)))
    raw = media.run(["ffmpeg", "-v", "error", "-i", path, "-an",
                     "-vf", "fps=%d,scale=%d:%d,format=gray" % (FPS, W, H),
                     "-f", "rawvideo", "-"], binary=True)
    frames = np.frombuffer(raw, dtype=np.uint8)
    n = len(frames) // (W * H)
    if n < 2:
        return np.zeros(seconds)
    frames = frames[:n * W * H].reshape(n, W * H).astype(float)
    diff = np.abs(np.diff(frames, axis=0)).mean(axis=1)
    diff = np.concatenate([[0.0], diff])
    per = len(diff) // FPS
    if per == 0:
        return np.zeros(seconds)
    return _fit(diff[:per * FPS].reshape(per, FPS).mean(axis=1), seconds)


def speech(segments, duration):
    """Words per second from transcript segments, with a bonus for ! and ?."""
    seconds = max(1, int(math.ceil(duration)))
    out = np.zeros(seconds)
    for seg in segments or []:
        a, b = int(seg["start"]), max(int(seg["start"]) + 1, int(math.ceil(seg["end"])))
        text = seg.get("text", "")
        weight = len(text.split()) + 2 * (text.count("!") + text.count("?"))
        a, b = max(0, a), min(seconds, b)
        if b > a:
            out[a:b] += weight / float(b - a)
    return out


def _z(x):
    """Robust z-score. A flat signal becomes zeros, never NaN."""
    x = np.asarray(x, dtype=float)
    med = np.median(x)
    spread = 1.4826 * np.median(np.abs(x - med))
    if spread < 1e-9:
        spread = x.std()
    if spread < 1e-9:
        return np.zeros_like(x)
    return np.clip((x - med) / spread, -3, 6)


def _smooth(x, k=5):
    if len(x) < 2:
        return x
    k = min(k, len(x))
    padded = np.pad(x, (k // 2, k - 1 - k // 2), mode="edge")
    return np.convolve(padded, np.ones(k) / k, mode="valid")


def score(loud, mot, spe=None):
    """Combine signals. Returns (scores, parts); weights renormalise over live signals."""
    loud = np.asarray(loud, dtype=float)
    onset = np.maximum(np.diff(loud, prepend=loud[:1]), 0)
    parts = {"loud": _z(loud), "onset": _z(onset), "motion": _z(mot)}
    if spe is not None:
        parts["speech"] = _z(spe)
    live = {k: v for k, v in parts.items() if np.any(v)}
    total = sum(WEIGHTS[k] for k in live)
    scores = np.zeros(len(loud))
    for key, value in live.items():
        scores += WEIGHTS[key] / total * value
    return _smooth(scores), parts
