import numpy as np

from hshorts import analyze, highlights, media


def run(path, **kw):
    info = media.probe(path)
    loud = analyze.loudness(path, info["duration"])
    mot = analyze.motion(path, info["duration"])
    scores, parts = analyze.score(loud, mot)
    return highlights.pick(scores, parts, loud, info["duration"], **kw), info


def test_burst_is_the_top_highlight(video):
    clips, _ = run(video, count=2, min_len=10, max_len=20)
    top = clips[0]
    assert top["start"] <= 32 and top["end"] >= 38
    assert 10 <= top["end"] - top["start"] <= 20
    assert "เสียง" in top["reason"] or "ภาพ" in top["reason"]


def test_video_without_audio_uses_motion(silent_video):
    clips, info = run(silent_video, count=1, min_len=10, max_len=20)
    assert not info["has_audio"]
    assert clips[0]["start"] <= 32 and clips[0]["end"] >= 38
    assert "ภาพ" in clips[0]["reason"]


def test_short_video_is_one_whole_clip(short_video):
    clips, info = run(short_video)
    assert len(clips) == 1
    assert clips[0]["start"] == 0
    assert abs(clips[0]["end"] - info["duration"]) < 0.5


def test_flat_signal_still_returns_clips():
    zeros = np.zeros(120)
    scores, parts = analyze.score(zeros, zeros)
    assert not np.isnan(scores).any()
    clips = highlights.pick(scores, parts, zeros, 120.0, count=3)
    assert len(clips) == 3


def test_windows_do_not_overlap_and_respect_bounds():
    rng = np.random.default_rng(1)
    loud, mot = rng.random(600) * 40, rng.random(600) * 10
    scores, parts = analyze.score(loud, mot)
    clips = highlights.pick(scores, parts, loud, 600.0, count=8, min_len=20, max_len=45)
    assert len(clips) == 8
    spans = sorted((c["start"], c["end"]) for c in clips)
    for (s1, e1), (s2, e2) in zip(spans, spans[1:]):
        assert e1 <= s2
    for s, e in spans:
        assert 20 <= e - s <= 45 and s >= 0 and e <= 600
    assert [c["score"] for c in clips] == sorted((c["score"] for c in clips), reverse=True)


def test_exclude_is_respected(video):
    first, _ = run(video, count=1, min_len=10, max_len=20)
    span = (first[0]["start"], first[0]["end"])
    more, _ = run(video, count=2, min_len=10, max_len=20, exclude=[span])
    for c in more:
        assert c["end"] <= span[0] or c["start"] >= span[1]


def test_max_len_is_capped_at_60():
    x = np.ones(300)
    x[100:200] = 50
    scores, parts = analyze.score(x, x)
    clips = highlights.pick(scores, parts, x, 300.0, count=1, min_len=20, max_len=500)
    assert clips[0]["end"] - clips[0]["start"] <= 60


def test_speech_signal_counts_words_and_excitement():
    s = analyze.speech([{"start": 2.0, "end": 4.0, "text": "no way! what?"}], 10)
    assert s[2] == s[3] > 0 and s[0] == 0 and s[5] == 0
    calm = analyze.speech([{"start": 2.0, "end": 4.0, "text": "no way what"}], 10)
    assert s[2] > calm[2]
