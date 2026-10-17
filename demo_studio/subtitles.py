"""Burned-in subtitles (style.subtitles): the narration on screen, for feeds that autoplay muted.

Each cue from captions.vtt is drawn as a transparent PNG with the overlay's own fonts (by
screenshotting a small HTML page), then the PNGs play as one image track (an ffconcat list
with exact cue times, a blank image in the gaps) overlaid on the video. Only the overlay
filter is used, so no ffmpeg build with libass or freetype is needed.
Framed videos show them on the wallpaper below the window; unframed ones above the caption.
"""
from __future__ import annotations

import base64
import html
from pathlib import Path

from .config import TEMPLATES


def _face() -> str:
    p = TEMPLATES / "fonts" / "mona-sans-var-latin.woff2"
    if not p.exists():
        return ""
    return ("@font-face{font-family:'DS Mona';font-weight:200 900;font-stretch:75% 125%;"
            f"src:url(data:font/woff2;base64,{base64.b64encode(p.read_bytes()).decode()}) format('woff2');}}")


def placement(size: tuple[int, int], frame: dict | None) -> dict:
    """Band (x, y, w, h) for the subtitles on the output canvas."""
    w, h = size
    k = min(w, h) / 1080
    if frame and frame.get("band"):
        top = frame["y"] + frame["h"] + int(10 * k)
        return {"x": 0, "y": top, "w": w, "h": max(2, frame["band"] - int(10 * k)) // 2 * 2, "k": k}
    bh = int(118 * k) // 2 * 2
    return {"x": 0, "y": h - bh - int(118 * k), "w": w, "h": bh, "k": k}


def _page(text: str, band: dict) -> str:
    k = band["k"]
    return (f"<!doctype html><html><head><style>{_face()}html,body{{margin:0;background:transparent}}"
            f"body{{width:{band['w']}px;height:{band['h']}px;display:flex;align-items:flex-start;justify-content:center}}"
            f"p{{margin:0;max-width:{int(band['w'] * 0.8)}px;padding:{int(9 * k)}px {int(20 * k)}px;border-radius:{int(12 * k)}px;"
            f"background:rgba(11,22,24,.80);color:#F1F5F4;font:560 {int(30 * k)}px/1.3 'DS Mona','Segoe UI',system-ui,sans-serif;"
            f"text-align:center;text-wrap:balance;letter-spacing:.003em;"
            f"box-shadow:0 0 0 1px rgba(255,255,255,.08),0 10px 30px rgba(0,0,0,.25)}}"
            f"</style></head><body><p>{html.escape(text)}</p></body></html>")


def render(cues: list[tuple[float, float, str]], total: float, band: dict, out: Path, log=print) -> Path:
    """Write subs/NNN.png and subs.ffconcat; returns the ffconcat path (relative names inside)."""
    from playwright.sync_api import sync_playwright
    from .tools import install_chromium
    d = out / "subs"
    d.mkdir(exist_ok=True)
    for old in d.glob("*.png"):
        old.unlink()
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception as e:
            if "Executable doesn't exist" not in str(e):
                raise
            install_chromium(log=log)
            browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": band["w"], "height": band["h"]}, device_scale_factor=1)
        page.set_content(f"<html><body style='margin:0;background:transparent'></body></html>")
        page.screenshot(path=str(d / "blank.png"), omit_background=True)
        for i, (_, _, text) in enumerate(cues):
            page.set_content(_page(text, band), wait_until="load")
            page.evaluate("document.fonts.ready")
            page.screenshot(path=str(d / f"{i:03d}.png"), omit_background=True)
        browser.close()
    lines, t = ["ffconcat version 1.0"], 0.0
    for i, (a, b, _) in enumerate(cues):
        if a > t + 0.001:
            lines += ["file 'subs/blank.png'", f"duration {a - t:.3f}"]
        lines += [f"file 'subs/{i:03d}.png'", f"duration {max(0.04, b - a):.3f}"]
        t = b
    if total > t:
        lines += ["file 'subs/blank.png'", f"duration {total - t + 0.5:.3f}"]
    lines.append("file 'subs/blank.png'")
    p = out / "subs.ffconcat"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p
