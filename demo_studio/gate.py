"""The quality gate (docs/quality-gate.md) and the run report.

Automated: text scan, audio timing/peak/silence, file probe, VTT, delivery and host results.
Manual: the frame review. `studio check` extracts a frame every 5 s plus contact sheets; the
reviewer records the verdict with `studio check <out> --frames pass --note "..."`.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from . import textscan
from .tools import ffmpeg, ffmpeg_stderr, probe


def _faststart(path: Path) -> bool:
    """True when the moov atom comes before mdat."""
    with open(path, "rb") as f:
        pos = 0
        size_total = path.stat().st_size
        while pos < size_total:
            f.seek(pos)
            hdr = f.read(16)
            if len(hdr) < 8:
                return False
            size = int.from_bytes(hdr[:4], "big")
            kind = hdr[4:8].decode("latin-1")
            if size == 1:
                size = int.from_bytes(hdr[8:16], "big")
            if kind == "moov":
                return True
            if kind == "mdat":
                return False
            if size < 8:
                return False
            pos += size
    return False


def _volume(path: Path) -> float:
    err = ffmpeg_stderr("-i", str(path), "-vn", "-af", "volumedetect", "-f", "null", "-")
    m = re.search(r"max_volume:\s*(-?[\d.]+) dB", err)
    return float(m.group(1)) if m else 0.0


def _silences(path: Path, min_len: float = 3.0) -> list[tuple[float, float]]:
    err = ffmpeg_stderr("-i", str(path), "-vn", "-af", f"silencedetect=noise=-45dB:d={min_len}", "-f", "null", "-")
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", err)]
    if len(ends) < len(starts):
        ends.append(float("inf"))
    return list(zip(starts, ends))


def parse_vtt(path: Path) -> list[tuple[float, float, str]]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("WEBVTT"):
        raise ValueError("missing WEBVTT header")
    cues = []
    for block in re.split(r"\n\s*\n", text.strip())[1:]:
        lines = block.strip().splitlines()
        tl = next((l for l in lines if "-->" in l), None)
        if not tl:
            raise ValueError(f"cue without timing: {block[:40]!r}")
        a, b = [x.strip().split(" ")[0] for x in tl.split("-->")]

        def secs(s):
            parts = s.split(":")
            return sum(float(p) * 60 ** i for i, p in enumerate(reversed(parts)))
        sa, sb_ = secs(a), secs(b)
        if sb_ <= sa:
            raise ValueError(f"cue ends before it starts: {tl}")
        cues.append((sa, sb_, " ".join(lines[lines.index(tl) + 1:])))
    for (a1, b1, _), (a2, _, _) in zip(cues, cues[1:]):
        if a2 < a1:
            raise ValueError("cues out of order")
    return cues


def extract_frames(out: Path, every: float = 5.0, size: tuple[int, int] = (1440, 900)) -> list[Path]:
    qa = out / "qa" / "frames"
    qa.mkdir(parents=True, exist_ok=True)
    for old in qa.glob("*.jpg"):
        old.unlink()
    ffmpeg("-i", "video.mp4", "-vf", f"fps=1/{every}", "-q:v", "3", str(qa / "t%03d.jpg"), cwd=out)
    frames = sorted(qa.glob("t*.jpg"))
    # Contact sheets: four frames per sheet, each 720 px wide, for a first pass.
    tw = 720
    th = int(round(tw * size[1] / size[0] / 2)) * 2
    sheets = out / "qa" / "sheets"
    sheets.mkdir(parents=True, exist_ok=True)
    for old in sheets.glob("*.jpg"):
        old.unlink()
    for i in range(0, len(frames), 4):
        group = frames[i:i + 4]
        inputs = []
        for f in group:
            inputs += ["-i", str(f)]
        while len(group) < 4:
            inputs += ["-f", "lavfi", "-i", f"color=c=black:s={size[0]}x{size[1]}:d=1"]
            group = group + [None]
        flt = (f"[0:v]scale={tw}:{th}[a];[1:v]scale={tw}:{th}[b];[2:v]scale={tw}:{th}[c];[3:v]scale={tw}:{th}[d];"
               "[a][b]hstack[top];[c][d]hstack[bot];[top][bot]vstack")
        ffmpeg(*inputs, "-filter_complex", flt, "-frames:v", "1", "-q:v", "3", str(sheets / f"sheet{i // 4 + 1:02d}.jpg"))
    return frames


def speech_check(out: Path, segs: list[dict]) -> dict:
    """Transcribe the final audio with faster-whisper and compare it with the script."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return {"ok": None, "note": "faster-whisper not installed; skipped"}
    import numpy as np
    import soundfile as sf
    a, sr = sf.read(out / "narration.wav", dtype="float32")
    if a.ndim > 1:
        a = a.mean(axis=1)
    n16 = int(len(a) * 16000 / sr)  # whisper wants 16 kHz; linear resampling is fine for a check
    a16 = np.interp(np.linspace(0, len(a) - 1, n16), np.arange(len(a)), a).astype(np.float32)
    model = WhisperModel("base.en", device="cpu", compute_type="int8")
    parts, _ = model.transcribe(a16, language="en", beam_size=5)
    heard = " ".join(p.text for p in parts)
    said = " ".join(s["text"] for s in segs if "text" in s)
    norm = lambda s: re.sub(r"[^a-z0-9 ]+", " ", s.lower()).split()
    ratio = SequenceMatcher(None, norm(said), norm(heard)).ratio()
    return {"ok": ratio >= 0.85, "similarity": round(ratio, 3), "heard": heard.strip()}


def run_checks(sb, out: Path, cost: str | None = None, frames_verdict: dict | None = None, speech: bool = True) -> dict:
    out = Path(out).resolve()
    info = json.loads((out / "timeline_out.json").read_text(encoding="utf-8"))
    segs, total = info["segments"], info["total"]
    strings = json.loads((out / "strings.json").read_text(encoding="utf-8")) if (out / "strings.json").exists() else []
    masked = json.loads((out / "masked.json").read_text(encoding="utf-8")) if (out / "masked.json").exists() else []
    res: dict = {"checked_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}

    size = tuple(info.get("size") or sb.viewport)
    # 1 frames
    frames = extract_frames(out, size=size)
    verdict_file = out / "qa" / "frames_verdict.json"
    if frames_verdict:
        verdict_file.write_text(json.dumps(frames_verdict, indent=2), encoding="utf-8")
    fv = json.loads(verdict_file.read_text(encoding="utf-8")) if verdict_file.exists() else None
    res["frames"] = {"count": len(frames), "ok": (fv or {}).get("verdict") == "pass" if fv else None,
                     "note": (fv or {}).get("note", "not reviewed yet")}

    # 2 text scan
    hits: list[str] = []
    for where, text in sb.on_screen_texts():
        hits += [h.safe() for h in textscan.find_dashes(text, where)]
    if sb.mode == "public":
        for s in strings:
            blob = "\n".join([s.get("title", ""), s.get("text", "")] + s.get("values", []) + s.get("attrs", []))
            for h in textscan.find_banned(blob, sb.banned_terms, f"screen@{s['where']}") + \
                    textscan.find_contacts(blob, f"screen@{s['where']}", sb.allowed_hosts):
                hits.append(h.safe())
        for where, text in sb.on_screen_texts():
            hits += [h.safe() for h in textscan.find_banned(text, sb.banned_terms, where)]
    secret_steps = sorted({s["where"] for s in strings if "[masked]" in json.dumps(s)})
    res["text"] = {"ok": not hits, "hits": hits, "screens_scanned": len(strings),
                   "masked_elements": len(masked), "steps_with_masked_text": secret_steps}

    # 3 audio
    timing = []
    for s in segs:
        if "narration_start" in s and (s["narration_start"] < s["start"] - 0.01 or s["narration_end"] > s["end"] + 0.01):
            timing.append(f"{s['id']}: narration {s['narration_start']}-{s['narration_end']} outside {s['start']}-{s['end']}")
    peak = _volume(out / "video.mp4")  # the final mix, music included
    slides = [(s["start"], s["end"]) for s in segs if s["kind"] == "slide"]
    long_sil = []
    voice = out / "narration.wav" if (out / "narration.wav").exists() else out / "video.mp4"
    for a, b in _silences(voice):  # the voice alone: music must not hide a gap in the narration
        b = min(b, total)
        outside = (b - a) - sum(max(0.0, min(b, e) - max(a, st)) for st, e in slides)
        if outside > 3.0:
            long_sil.append(f"{a:.1f}-{b:.1f}s ({outside:.1f}s outside slides)")
    res["audio"] = {"ok": not timing and peak < -1.0 and not long_sil, "peak_db": peak,
                    "timing_issues": timing, "long_silences": long_sil}
    if speech:
        res["audio"]["speech"] = speech_check(out, segs)
        if res["audio"]["speech"]["ok"] is False:
            res["audio"]["ok"] = False

    # 4 file
    pr = probe(out / "video.mp4")
    v, a = pr["video"], pr["audio"]
    dur = float(pr["duration"] or 0)
    w, h = size
    vtt_ok, vtt_note = True, ""
    try:
        cues = parse_vtt(out / "captions.vtt")
        vtt_note = f"{len(cues)} cues"
    except Exception as e:
        vtt_ok, vtt_note = False, str(e)
    file_checks = {
        "h264": v.get("codec") == "h264", "aac": a.get("codec") == "aac",
        "size": (v.get("width"), v.get("height")) == (w, h), "faststart": _faststart(out / "video.mp4"),
        "duration": abs(dur - total) <= 0.05 * total, "poster": (out / "poster.jpg").exists(), "vtt": vtt_ok,
    }
    res["file"] = {"ok": all(file_checks.values()), **file_checks, "duration_s": round(dur, 2),
                   "timeline_s": total, "vtt_note": vtt_note, "size_mb": round((out / "video.mp4").stat().st_size / 1e6, 2)}

    # 5, 6 delivery and VPS (written by `studio publish`)
    dl = out / "delivery.json"
    if dl.exists():
        d = json.loads(dl.read_text(encoding="utf-8"))
        res["delivery"] = {"ok": d.get("ok"), **{k: v for k, v in d.items() if k != "ok"}}
    elif sb.delivery.get("local_only"):
        res["delivery"] = {"ok": True, "note": "local only by design: you deliver the MP4 yourself"}
    else:
        res["delivery"] = {"ok": None, "note": "not published yet"}

    # 6 the publishing server unchanged apart from demo-studio's own parts. Only when the
    # settings ask for it (publish.host_check: true); the operator records out/vps_check.json.
    from .config import out_root, settings
    vc = out_root() / "vps_check.json"
    uses_server = res["delivery"].get("kind") in ("public", "private") and res["delivery"].get("target") != "folder"
    if uses_server and settings().get("publish", {}).get("host_check"):
        res["vps"] = json.loads(vc.read_text(encoding="utf-8")) if vc.exists() else {"ok": None, "note": "no snapshot comparison recorded"}
    else:
        res["vps"] = {"ok": True, "note": "no server check configured for this video"}

    res["cost"] = cost or "not recorded"
    res["vps"].setdefault("ok", None)
    parts = [res["frames"]["ok"], res["text"]["ok"], res["audio"]["ok"], res["file"]["ok"], res["delivery"]["ok"], res["vps"]["ok"]]
    res["passed"] = all(p is True for p in parts)
    (out / "qa" / "gate.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    write_report(sb, out, info, res, masked)
    return res


def _mark(ok) -> str:
    return {True: "PASS", False: "FAIL", None: "PENDING"}[ok]


def write_report(sb, out: Path, info: dict, res: dict, masked: list) -> None:
    segs = info["segments"]
    L = [f"# Run report: {sb.name}", "",
         f"- Mode: **{sb.mode}**" + (f" (client folder `{sb.client}`)" if sb.mode == "handover" else ""),
         f"- Storyboard: `{Path(sb.path).name}`",
         f"- Checked: {res['checked_at']}",
         f"- Gate: **{'PASSED' if res['passed'] else 'NOT PASSED'}**", "",
         "## Durations", "", "| Part | Start | End | Length | Narration |", "|---|---|---|---|---|"]
    for s in segs:
        nar = f"{s['narration_end'] - s['narration_start']:.1f}s" if "narration_start" in s else "-"
        name = {"_intro": "intro slide", "_outro": "outro slide"}.get(s["id"], s["id"])
        L.append(f"| {name} | {s['start']:.1f}s | {s['end']:.1f}s | {s['end'] - s['start']:.1f}s | {nar} |")
    L += ["", f"Total: **{info['total']:.1f}s**, {info['frames']} captured frames, {info['cues']} caption cues, "
          f"narration gain {info['audio']['gain_db']} dB to a {info['audio']['peak_dbfs']} dBFS peak.", ""]
    L += ["## Masked", ""]
    if masked:
        by = {}
        for m in masked:
            by.setdefault((m["where"], m["why"], m["tag"]), 0)
            by[(m["where"], m["why"], m["tag"])] += 1
        L += [f"- {w}: {n} x `{t}` ({why})" for (w, why, t), n in sorted(by.items())]
    else:
        L.append("- Nothing matched the secret patterns. Selector masks (passwords, key and token fields) were active throughout.")
    L += ["", "## Sources", ""] + [f"- {s}" for s in sb.sources]
    L += ["", "## Gate", "",
          f"1. Frames: **{_mark(res['frames']['ok'])}**: {res['frames']['count']} frames (one every 5 s) in `qa/frames/`, "
          f"sheets in `qa/sheets/`. {res['frames']['note']}",
          f"2. Text scan: **{_mark(res['text']['ok'])}**: {res['text']['screens_scanned']} screens scanned"
          + (f"; hits: {'; '.join(res['text']['hits'])}" if res['text']['hits'] else "; no hits") + ".",
          f"3. Audio: **{_mark(res['audio']['ok'])}**: peak {res['audio']['peak_db']} dB; "
          f"timing {'OK' if not res['audio']['timing_issues'] else res['audio']['timing_issues']}; "
          f"silences over 3 s outside slides: {res['audio']['long_silences'] or 'none'}"
          + (f"; speech check similarity {res['audio']['speech'].get('similarity')}" if res['audio'].get('speech') else "") + ".",
          f"4. File: **{_mark(res['file']['ok'])}**: " + ", ".join(
              f"{k} {'ok' if res['file'][k] else 'FAIL'}" for k in ("h264", "aac", "size", "faststart", "duration", "poster", "vtt"))
          + f"; {res['file']['duration_s']}s vs timeline {res['file']['timeline_s']}s; {res['file']['size_mb']} MB; {res['file']['vtt_note']}.",
          f"5. Delivery: **{_mark(res['delivery']['ok'])}**: " + json.dumps({k: v for k, v in res['delivery'].items() if k != 'ok'}),
          f"6. Server unchanged apart from demo-studio's own parts: **{_mark(res['vps']['ok'])}**: " + json.dumps({k: v for k, v in res['vps'].items() if k != 'ok'}),
          f"7. Cost: {res['cost']}", ""]
    (out / "REPORT.md").write_text("\n".join(L), encoding="utf-8")
