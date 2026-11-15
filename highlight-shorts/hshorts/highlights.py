"""Pick highlight windows from a per-second score."""
import numpy as np

REASONS = {
    "loud": "เสียงดังกว่าปกติ",
    "onset": "เสียงพุ่งขึ้นกะทันหัน",
    "motion": "ภาพเคลื่อนไหวเร็ว",
    "speech": "คนเล่นพูดเยอะหรือตื่นเต้น",
}
SNAP = 3


def _overlaps(a, b, taken):
    return any(a < e and s < b for s, e in taken)


def _snap(edge, loud, lo, hi):
    """Move an edge to the quietest second nearby, staying inside [lo, hi]."""
    lo, hi = max(lo, edge - SNAP), min(hi, edge + SNAP)
    if hi <= lo:
        return edge
    span = loud[lo:hi + 1] if hi < len(loud) else loud[lo:]
    if len(span) == 0 or not np.any(span):
        return edge
    return lo + int(np.argmin(span))


def _reason(parts, a, b):
    means = {k: float(v[a:b].mean()) for k, v in parts.items() if b > a}
    top = [k for k, v in sorted(means.items(), key=lambda kv: -kv[1]) if v > 0.5][:2]
    if not top:
        return "ช่วงที่คะแนนรวมสูงสุดของวิดีโอ"
    return " + ".join(REASONS[k] for k in top)


def pick(scores, parts, loud, duration, count=8, min_len=20, max_len=45, exclude=()):
    scores = np.asarray(scores, dtype=float)
    n = len(scores)
    total = int(min(n, max(1, round(duration))))
    max_len = int(min(max_len, 60))
    min_len = int(min(min_len, max_len))
    taken = [(int(s), int(e)) for s, e in exclude]
    if total <= min_len:
        if _overlaps(0, total, taken):
            return []
        return [{"start": 0.0, "end": float(min(duration, total)),
                 "score": float(scores[:total].mean()) if total else 0.0,
                 "reason": _reason(parts, 0, total)}]
    floor = float(np.median(scores))
    out = []
    for peak in np.argsort(-scores[:total], kind="stable"):
        if len(out) >= count:
            break
        peak = int(peak)
        if _overlaps(peak, peak + 1, taken):
            continue
        a, b = peak, peak + 1
        while b - a < max_len:
            left = scores[a - 1] if a > 0 and not _overlaps(a - 1, a, taken) else -np.inf
            right = scores[b] if b < total and not _overlaps(b, b + 1, taken) else -np.inf
            if left == -np.inf and right == -np.inf:
                break
            if b - a >= min_len and max(left, right) <= floor:
                break
            if left >= right:
                a -= 1
            else:
                b += 1
        if b - a < min_len:
            continue
        a2 = _snap(a, loud, 0, a + SNAP)
        b2 = _snap(b, loud, b - SNAP, total)
        if min_len <= b2 - a2 <= max_len and not _overlaps(a2, b2, taken):
            a, b = a2, b2
        taken.append((a, b))
        out.append({"start": float(a), "end": float(min(b, duration)),
                    "score": round(float(scores[a:b].mean()), 3),
                    "reason": _reason(parts, a, b)})
    out.sort(key=lambda c: -c["score"])
    return out
