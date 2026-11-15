"""Build and run the ffmpeg command that makes one vertical clip."""
import os

from . import media

OUT_W, OUT_H, MAX_SECONDS = 1080, 1920, 60


def build_cmd(src, out, start, end, crop_mode="crop", crop_x=0.5, voice=None, duck=0.2,
              ass=None, has_audio=True):
    """`ass` must be a bare file name; ffmpeg is run from that file's folder."""
    length = float(end) - float(start)
    if length <= 0:
        raise ValueError("clip end must be after its start")
    if length > MAX_SECONDS + 0.01:
        raise ValueError("a Short can be at most %d seconds" % MAX_SECONDS)
    crop_x = min(1.0, max(0.0, float(crop_x)))
    duck = min(1.0, max(0.0, float(duck)))
    cmd = ["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % float(start), "-t", "%.3f" % length,
           "-i", src]
    nxt = 1
    voice_i = silence_i = None
    if voice:
        cmd += ["-i", voice]
        voice_i, nxt = nxt, nxt + 1
    if not has_audio and not voice:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        silence_i = nxt
    fill = "scale=%d:%d:force_original_aspect_ratio=increase" % (OUT_W, OUT_H)
    if crop_mode == "blur":
        vf = ("[0:v]split[b0][f0];[b0]%s,crop=%d:%d,boxblur=20:2[bg];"
              "[f0]scale=%d:%d:force_original_aspect_ratio=decrease[fg];"
              "[bg][fg]overlay=(W-w)/2:(H-h)/2" % (fill, OUT_W, OUT_H, OUT_W, OUT_H))
    else:
        vf = "[0:v]%s,crop=%d:%d:(iw-%d)*%.4f:(ih-%d)/2" % (fill, OUT_W, OUT_H, OUT_W,
                                                             crop_x, OUT_H)
    vf += ",setsar=1"
    if ass:
        vf += ",ass=%s" % ass
    vf += "[v]"
    if voice and has_audio:
        af = ("[0:a]volume=%.3f[orig];[%d:a]apad[vo];"
              "[orig][vo]amix=inputs=2:duration=first:normalize=0[a]" % (duck, voice_i))
    elif voice:
        af = "[%d:a]apad[a]" % voice_i
    elif has_audio:
        af = "[0:a]anull[a]"
    else:
        af = "[%d:a]anull[a]" % silence_i
    cmd += ["-filter_complex", vf + ";" + af, "-map", "[v]", "-map", "[a]",
            "-t", "%.3f" % length, "-r", "30",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart", out]
    return cmd


def render_clip(src, out, start, end, crop_mode="crop", crop_x=0.5, voice=None, duck=0.2,
                ass=None):
    """`ass` is a full path here; only its file name reaches the filter string."""
    has_audio = media.probe(src)["has_audio"]
    cwd, name = (os.path.dirname(os.path.abspath(ass)), os.path.basename(ass)) if ass else (None, None)
    cmd = build_cmd(os.path.abspath(src), os.path.abspath(out), start, end, crop_mode, crop_x,
                    os.path.abspath(voice) if voice else None, duck, name, has_audio)
    media.run(cmd, cwd=cwd)
    return out
