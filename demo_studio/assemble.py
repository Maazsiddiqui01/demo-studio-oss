"""ffmpeg assembly: frames + timeline + narration -> video.mp4, captions.vtt, poster.jpg.

Sped-up waits are applied per frame: a frame inside a wait window plays for 1/factor of its
real duration, and the narration offsets are mapped onto the same output clock.
With style.frame the recording is composited onto a wallpaper (style.py); with style.music a
quiet bed is mixed under the voice (music.py). narration.wav always holds the voice alone,
so the gate's silence check is not fooled by the music.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import numpy as np
import soundfile as sf

from .config import FPS, LEAD_IN
from .tools import ffmpeg
from .tts import SR

PEAK_DBFS = -2.5
MIX_PEAK_DBFS = -1.5   # the final mix (voice plus music) stays below this
SLIDE_FADE = 0.6


class Clock:
    """Maps recording wall-clock time to output time."""

    def __init__(self, timeline: dict):
        self.t0 = timeline["start"]
        self.waits = [(w["start"], w["end"], w["factor"]) for w in timeline["waits"] if w.get("end")]

    def __call__(self, t: float) -> float:
        x = t - self.t0
        for a, b, f in self.waits:
            ov = min(t, b) - max(self.t0, a)
            if ov > 0:
                x -= ov * (1 - 1 / f)
        return max(0.0, x)


def output_segments(timeline: dict, narr: dict) -> tuple[list[dict], float]:
    clk = Clock(timeline)
    segs = []
    for m in timeline["marks"]:
        start, end = clk(m["start"]), clk(m["end"])
        lid = m["id"]
        n = narr.get(lid)
        seg = {"id": lid, "kind": m["kind"], "start": round(start, 3), "end": round(end, 3)}
        if n:
            ns = start + LEAD_IN + (SLIDE_FADE if lid == "_outro" else 0.0)
            seg.update(narration_start=round(ns, 3), narration_end=round(ns + n["seconds"], 3), text=n["text"])
        segs.append(seg)
    segs[0]["start"] = 0.0
    total = clk(timeline["end"])
    return segs, round(total, 3)


def write_concat(timeline: dict, out: Path) -> Path:
    clk = Clock(timeline)
    frames = timeline["frames"]
    lines = ["ffconcat version 1.0"]
    for i, (ts, idx) in enumerate(frames):
        nxt = frames[i + 1][0] if i + 1 < len(frames) else timeline["end"]
        dur = max(0.0, clk(nxt) - clk(ts))
        lines.append(f"file 'frames/{idx:06d}.jpg'")
        lines.append(f"duration {dur:.6f}")
    lines.append(f"file 'frames/{frames[-1][1]:06d}.jpg'")
    p = out / "frames.ffconcat"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def mix_audio(segs: list[dict], narr: dict, total: float, dest: Path) -> tuple[dict, np.ndarray]:
    buf = np.zeros(int((total + 0.5) * SR), dtype=np.float32)
    for s in segs:
        n = narr.get(s["id"])
        if not n:
            continue
        a, sr = sf.read(n["path"], dtype="float32")
        assert sr == SR
        i = int(s["narration_start"] * SR)
        j = min(buf.size, i + a.size)
        buf[i:j] += a[: j - i]
    buf = buf[: int(total * SR)]
    peak = float(np.abs(buf).max()) or 1.0
    gain = (10 ** (PEAK_DBFS / 20)) / peak
    buf *= gain
    sf.write(dest, buf, SR, subtype="PCM_16")
    return {"gain_db": round(20 * np.log10(gain), 2), "peak_dbfs": PEAK_DBFS}, buf


def add_music(sb, segs: list[dict], voice: np.ndarray, total: float, dest: Path) -> dict:
    """Voice plus the ducked music bed, written to dest. Returns what was mixed."""
    from .music import bed
    st = sb.style
    spans = [(s["narration_start"], s["narration_end"]) for s in segs if "narration_start" in s]
    m = bed(st.music, total, SR, spans, st.music_db, st.duck_db, base_dir=Path(sb.path).parent)[: voice.size]
    mix = voice.copy()
    mix[: m.size] += m
    peak = float(np.abs(mix).max()) or 1.0
    limit = 10 ** (MIX_PEAK_DBFS / 20)
    trim = min(1.0, limit / peak)
    mix *= trim
    sf.write(dest, mix, SR, subtype="PCM_16")
    return {"music": st.music, "music_db": st.music_db, "duck_db": st.duck_db,
            "mix_trim_db": round(20 * np.log10(trim), 2)}


def _cues(text: str, start: float, end: float) -> list[tuple[float, float, str]]:
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    parts = []
    for s in sents:
        if len(s) <= 90:
            parts.append(s)
            continue
        chunk = ""
        for piece in re.split(r"(?<=,)\s+", s):
            if chunk and len(chunk) + len(piece) > 90:
                parts.append(chunk)
                chunk = piece
            else:
                chunk = f"{chunk} {piece}".strip()
        if chunk:
            parts.append(chunk)
    total_chars = sum(len(p) for p in parts) or 1
    out, t = [], start
    for p in parts:
        d = (end - start) * len(p) / total_chars
        out.append((t, t + d, p))
        t += d
    return out


def _ts(t: float) -> str:
    h, rem = divmod(max(0.0, t), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def all_cues(segs: list[dict]) -> list[tuple[float, float, str]]:
    out = []
    for s in segs:
        if "narration_start" in s:
            out += _cues(s["text"], s["narration_start"], s["narration_end"])
    return out


def write_vtt(segs: list[dict], dest: Path) -> int:
    lines = ["WEBVTT", ""]
    cues = all_cues(segs)
    for n, (a, b, text) in enumerate(cues, 1):
        lines += [str(n), f"{_ts(a)} --> {_ts(b)}", text, ""]
    dest.write_text("\n".join(lines), encoding="utf-8")
    return len(cues)


def assemble(sb, timeline: dict, narr: dict, out: Path, keep_frames: bool = False, log=print) -> dict:
    segs, total = output_segments(timeline, narr)
    if not 1 < total < 1800:
        raise RuntimeError(f"timeline total is {total:.1f}s; refusing to assemble (clock problem?)")
    concat = write_concat(timeline, out)
    voice_wav = out / "narration.wav"
    audio, voice = mix_audio(segs, narr, total, voice_wav)
    mix = voice_wav
    (out / "mix.wav").unlink(missing_ok=True)
    if sb.style.music:
        mix = out / "mix.wav"
        audio.update(add_music(sb, segs, voice, total, mix))
    cue_count = write_vtt(segs, out / "captions.vtt")
    video = out / "video.mp4"
    inputs = ["-f", "concat", "-safe", "0", "-i", concat.name, "-i", mix.name]
    frame = None
    if sb.style.frame:
        from .style import filter_graph, frame_assets
        frame = frame_assets(sb.style, sb.viewport, Path(sb.path).parent, name=sb.name, log=log)
        for layer in ("wallpaper", "window", "mask"):  # looped stills, cut a second past the end
            inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{total + 1:.3f}", "-i", frame[layer]]
        vf = filter_graph(frame, FPS)
        w, h = frame["canvas"]
        log(f"  encoding {total:.1f}s at {w}x{h} (framed on {frame['background']}, recording at {frame['w']}x{frame['h']}), {FPS} fps")
        if frame["scale"] < 1:
            from .style import fits_1to1
            fw, fh = fits_1to1(sb.style, sb.viewport)
            log(f"  tip: the recording is scaled to {frame['scale']:.0%}; viewport [{fw}, {fh}] would fit 1:1 (sharpest text)")
    else:
        w, h = sb.viewport
        vf = f"[0:v]fps={FPS},scale={w}:{h}:flags=lanczos[base]"
        log(f"  encoding {total:.1f}s at {w}x{h}, {FPS} fps")
    if sb.style.subtitles:
        from . import subtitles
        band = subtitles.placement((w, h), frame)
        subs = subtitles.render(all_cues(segs), total, band, out, log=log)
        inputs += ["-f", "concat", "-safe", "0", "-i", subs.name]
        n_in = 5 if frame else 2
        vf += f";[{n_in}:v]format=rgba[subs];[base][subs]overlay={band['x']}:{band['y']}:eof_action=pass[sbase]"
        vf += ";[sbase]format=yuv420p[v]"
        log(f"  burning in {cue_count} subtitle cues")
    else:
        vf += ";[base]format=yuv420p[v]"
    ffmpeg(
        *inputs,
        "-filter_complex", f"{vf};[1:a]aresample=48000[a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-g", str(FPS * 2), "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
        "-movflags", "+faststart", "-t", f"{total:.3f}", video.name,
        cwd=out,
    )
    # poster
    # poster: "intro", "<step id>" (just before the step ends) or "<step id>@<seconds into the step>"
    pid, _, at = str(sb.poster).partition("@")
    if pid == "intro":
        intro = next(s for s in segs if s["id"] == "_intro")
        pt = max(0.5, intro["end"] - 0.3)
    else:
        seg = next((s for s in segs if s["id"] == pid), segs[1])
        pt = seg["start"] + float(at) if at else seg["end"] - 0.6
        pt = max(0.5, min(pt, seg["end"] - 0.1))
    ffmpeg("-ss", f"{pt:.3f}", "-i", video.name, "-frames:v", "1", "-q:v", "2", "poster.jpg", cwd=out)
    info = {"total": total, "segments": segs, "audio": audio, "cues": cue_count,
            "frames": len(timeline["frames"]), "poster_at": round(pt, 3), "size": [w, h],
            "frame": {k: frame[k] for k in ("canvas", "scale", "w", "h", "x", "y", "bar", "band", "background", "motion")} if frame else None,
            "subtitles": bool(sb.style.subtitles)}
    (out / "timeline_out.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    if not keep_frames:
        shutil.rmtree(out / "frames", ignore_errors=True)
        shutil.rmtree(out / "subs", ignore_errors=True)
        concat.unlink(missing_ok=True)
        (out / "subs.ffconcat").unlink(missing_ok=True)
    return info
