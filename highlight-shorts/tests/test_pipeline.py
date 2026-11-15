import pytest

from hshorts import pipeline, store, upload


def make(video, **kw):
    args = dict(url="", file_path=video, channel="RockstarFan", permission=True,
                settings={"count": 2, "min_len": 10, "max_len": 20})
    args.update(kw)
    return store.create(**args)


def test_permission_and_credit_are_required(data_dir, video):
    with pytest.raises(ValueError):
        make(video, permission=False)
    with pytest.raises(ValueError):
        make(video, permission="yes")
    with pytest.raises(ValueError):
        make(video, channel="  ")
    with pytest.raises(ValueError):
        make(video, url="ftp://x/y", file_path="")
    with pytest.raises(ValueError):
        make(video, url="https://youtu.be/x")
    assert store.all() == []


def test_settings_are_clamped(data_dir, video):
    p = make(video, settings={"count": 99, "min_len": 50, "max_len": 500})
    assert p["settings"] == {"count": 30, "min_len": 50, "max_len": 60, "use_speech": False}


def test_process_local_file_picks_highlights(data_dir, video):
    p = make(video)
    pipeline.process(p["id"])
    p = store.load(p["id"])
    assert p["status"]["stage"] == "ready", p["status"]
    assert p["title"] == "game" and abs(p["duration"] - 60) < 1
    assert len(p["clips"]) == 2
    top = p["clips"][0]
    assert top["start"] <= 32 and top["end"] >= 38 and top["id"] == "c1"
    assert not top["has_voice"] and "#Shorts" in top["title"]
    before = [(c["start"], c["end"]) for c in p["clips"]]
    p = pipeline.add_more(p["id"], 1)
    assert len(p["clips"]) == 3 and p["clips"][2]["id"] == "c3"
    s, e = p["clips"][2]["start"], p["clips"][2]["end"]
    assert all(e <= a or s >= b for a, b in before)


def test_missing_file_ends_in_error_not_a_crash(data_dir):
    p = make("/nope/missing.mp4")
    pipeline.process(p["id"])
    status = store.load(p["id"])["status"]
    assert status["stage"] == "error" and "missing.mp4" in status["error"]


def test_bad_project_id_cannot_escape_the_data_folder(data_dir):
    with pytest.raises(KeyError):
        store.load("../../etc")


def test_description_carries_credit_and_link():
    text = upload.describe("มันส์มาก", "RockstarFan", "https://youtu.be/abc")
    assert text.startswith("มันส์มาก")
    assert "RockstarFan" in text and "https://youtu.be/abc" in text and "ได้รับอนุญาต" in text


def test_upload_body_is_always_private():
    b = upload.body("t" * 300, "d", ["a", "", "b"])
    assert b["status"]["privacyStatus"] == "private"
    assert len(b["snippet"]["title"]) == 100 and b["snippet"]["tags"] == ["a", "b"]
