import subprocess

import pytest

from hshorts import media, render, subtitles


def check(path, seconds):
    info = media.probe(path)
    assert (info["width"], info["height"]) == (1080, 1920)
    assert info["has_audio"]
    assert abs(info["duration"] - seconds) < 0.4


@pytest.fixture()
def voice(tmp_path):
    path = str(tmp_path / "voice.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=3", path], check=True)
    return path


@pytest.mark.parametrize("mode", ["crop", "blur"])
def test_clip_is_vertical_with_audio(video, tmp_path, mode):
    out = render.render_clip(video, str(tmp_path / "o.mp4"), 28, 34, crop_mode=mode, crop_x=0.8)
    check(out, 6)


def test_voice_and_thai_subtitles_with_awkward_characters(video, voice, tmp_path):
    folder = tmp_path / "โฟลเดอร์ it's: [1]"
    folder.mkdir()
    ass = str(folder / "c1.ass")
    subtitles.write_ass([{"start": 0, "end": 2, "text": "ยิงกันสนั่น! {wow} C:\\path 'q': ok"},
                         {"start": 2, "end": 4, "text": "ไล่ล่ากันทั้งเมืองแบบไม่มีใครยอมใครเลยจริงๆนะครับทุกคน"}],
                        ass)
    out = render.render_clip(video, str(folder / "o.mp4"), 28, 33, voice=voice, duck=0.2, ass=ass)
    check(out, 5)


def test_voice_shorter_than_clip_keeps_full_length(video, voice, tmp_path):
    check(render.render_clip(video, str(tmp_path / "o.mp4"), 10, 18, voice=voice), 8)


def test_source_without_audio(silent_video, voice, tmp_path):
    check(render.render_clip(silent_video, str(tmp_path / "a.mp4"), 5, 9), 4)
    check(render.render_clip(silent_video, str(tmp_path / "b.mp4"), 5, 9, voice=voice), 4)


def test_over_60_seconds_is_refused():
    with pytest.raises(ValueError):
        render.build_cmd("a.mp4", "b.mp4", 0, 61)
    with pytest.raises(ValueError):
        render.build_cmd("a.mp4", "b.mp4", 5, 5)


def test_ass_escapes_and_wraps():
    lines = subtitles.wrap("ไล่ล่ากันทั้งเมืองแบบไม่มีใครยอมใครเลยจริงๆนะครับทุกคน")
    assert len(lines) > 1 and all(len(x) <= subtitles.WIDTH + 3 for x in lines)
    assert all(x[0] not in subtitles.THAI_MARKS for x in lines)
    assert subtitles.wrap("one two three") == ["one two three"]
    assert subtitles._escape("{a}\\b") == "\\{a\\}\uff3cb"
    assert subtitles._stamp(3725.5) == "1:02:05.50"
