"""Voiceover transcription (Whisper, on this machine) and the ASS subtitle file."""
import os

WIDTH = 24
THAI_MARKS = set("\u0e31\u0e34\u0e35\u0e36\u0e37\u0e38\u0e39\u0e3a"
                 "\u0e47\u0e48\u0e49\u0e4a\u0e4b\u0e4c\u0e4d\u0e4e")
_models = {}


def transcribe(audio_path, language=None, model="small"):
    """Return [{start, end, text}]. Needs the faster-whisper package."""
    from faster_whisper import WhisperModel
    name = os.environ.get("HS_WHISPER", model)
    if name not in _models:
        _models[name] = WhisperModel(name, device="cpu", compute_type="int8")
    segments, _ = _models[name].transcribe(audio_path, language=language, vad_filter=True)
    return [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
            for s in segments if s.text.strip()]


def _chunks(word):
    """Hard-split a long run with no spaces (Thai), never before a combining mark."""
    out, cur = [], ""
    for ch in word:
        if len(cur) >= WIDTH and ch not in THAI_MARKS:
            out.append(cur)
            cur = ""
        cur += ch
    if cur:
        out.append(cur)
    return out


def wrap(text):
    lines, cur = [], ""
    for word in " ".join(text.split()).split(" "):
        for piece in _chunks(word) or [""]:
            if cur and len(cur) + 1 + len(piece) > WIDTH:
                lines.append(cur)
                cur = piece
            else:
                cur = (cur + " " + piece).strip()
    if cur:
        lines.append(cur)
    return lines


def _escape(line):
    return line.replace("\\", "\uff3c").replace("{", "\\{").replace("}", "\\}")


def _stamp(t):
    t = max(0.0, float(t))
    cs = int(round(t * 100))
    return "%d:%02d:%02d.%02d" % (cs // 360000, cs // 6000 % 60, cs // 100 % 60, cs % 100)


def write_ass(subs, path, font=None):
    font = font or os.environ.get("HS_FONT", "Noto Sans Thai")
    head = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,%s,72,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,"
        "0,0,1,4,1,2,60,60,260,1\n\n[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        % font.replace(",", " "))
    rows = []
    for sub in subs or []:
        text = "\\N".join(_escape(line) for line in wrap(sub.get("text", "")))
        if text and float(sub["end"]) > float(sub["start"]):
            rows.append("Dialogue: 0,%s,%s,Default,,0,0,0,,%s"
                        % (_stamp(sub["start"]), _stamp(sub["end"]), text))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(head + "\n".join(rows) + "\n")
