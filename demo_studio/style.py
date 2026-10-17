"""The framed look: the recording sits on a wallpaper, with rounded corners and a soft shadow.

Three images are drawn by screenshotting small HTML pages with Playwright (no image library):
  wallpaper.png  the background, a little larger than the canvas so it can drift
  window.png     the window's shadow, optional border and optional title bar, on transparency
  mask.png       a white rounded rectangle the size of the recording
ffmpeg merges the mask into the recording as alpha, slowly pans the wallpaper (style.motion:
drift), lays the window layer on it and the recording on top. Only crop, overlay and
alphamerge are used, so ffmpeg 4.4 works too.

The recording fills the frame: the window always reaches the padding line, so the wallpaper is a
thin margin. `viewport: auto` sizes a browser to fill the canvas at exactly 1:1 (sharpest text). A
smaller recording, such as a desktop app window, is scaled up to fill (style.fill: auto, up to
2x); style.fill: false keeps it at 1:1 with more wallpaper around it.
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
from pathlib import Path

from .config import TEMPLATES, cache_dir


def _mesh(base: str, *blobs: tuple[str, int, int, int]) -> str:
    """Soft colour fields: (colour, x %, y %, size px) over a base colour."""
    out = []
    for c, x, y, s in blobs:
        s = int(s * 1.35)  # large, overlapping fields with a long falloff blend into a mesh
        out.append(f"radial-gradient({s}px {int(s * .8)}px at {x}% {y}%, {c} 0%, "
                   f"color-mix(in srgb, {c} 45%, transparent) 32%, transparent 72%)")
    return ",".join(out) + f", {base}"


# Original generated wallpapers (no photographs, nothing to license), grouped like a picker.
BACKGROUNDS: dict[str, tuple[str, str]] = {  # name: (category, CSS background)
    "aurora": ("dark", _mesh("#0a0f24", ("#2f6bff", 12, 18, 1100), ("#8b5cf6", 88, 22, 900), ("#06b6d4", 62, 108, 1200))),
    "midnight": ("dark", _mesh("#020617", ("#1e293b", 50, 0, 1300), ("#0f2a3d", 90, 100, 900))),
    "graphite": ("dark", _mesh("#111315", ("#2b2f36", 20, 15, 1100), ("#3a3f47", 85, 85, 1000), ("#1c1f24", 60, 40, 700))),
    "nebula": ("dark", _mesh("#0b0718", ("#7c3aed", 15, 80, 1000), ("#db2777", 85, 20, 900), ("#1d4ed8", 55, 55, 800))),
    "ocean": ("blue", _mesh("#06202f", ("#0ea5e9", 15, 20, 1100), ("#14b8a6", 85, 80, 1000))),
    "lagoon": ("blue", _mesh("#042f2e", ("#2dd4bf", 20, 85, 1100), ("#0284c7", 80, 15, 1000), ("#0f766e", 50, 50, 700))),
    "sky": ("blue", _mesh("#1e3a8a", ("#60a5fa", 25, 20, 1200), ("#a5b4fc", 85, 70, 1000), ("#38bdf8", 55, 100, 900))),
    "blueprint": ("blue", "linear-gradient(rgba(255,255,255,.07) 1px, transparent 1px) 0 0/48px 48px,"
                          "linear-gradient(90deg, rgba(255,255,255,.07) 1px, transparent 1px) 0 0/48px 48px,"
                          + _mesh("#0b3a75", ("#1d64c2", 30, 30, 1200), ("#0a2c5c", 85, 90, 1000))),
    "dusk": ("purple", _mesh("#1e1037", ("#a855f7", 15, 25, 1100), ("#f472b6", 90, 75, 1000), ("#6366f1", 60, 0, 900))),
    "violet": ("purple", _mesh("#2e1065", ("#8b5cf6", 30, 70, 1200), ("#c084fc", 80, 20, 900))),
    "orchid": ("purple", _mesh("#3b0a45", ("#e879f9", 20, 20, 1000), ("#a21caf", 80, 80, 1100), ("#f0abfc", 70, 15, 600))),
    "sunset": ("orange", _mesh("#1c0d24", ("#fb923c", 10, 15, 1000), ("#ec4899", 90, 25, 1000), ("#7c3aed", 50, 110, 1200))),
    "ember": ("orange", _mesh("#1a0a04", ("#ea580c", 20, 80, 1200), ("#f59e0b", 85, 20, 900), ("#b91c1c", 70, 90, 800))),
    "citrus": ("orange", _mesh("#7c2d12", ("#fdba74", 25, 20, 1100), ("#facc15", 85, 75, 1000), ("#fb7185", 60, 105, 900))),
    "forest": ("green", _mesh("#052e16", ("#16a34a", 20, 80, 1100), ("#0d9488", 85, 20, 1000))),
    "mint": ("green", _mesh("#0f3d33", ("#34d399", 25, 25, 1100), ("#a7f3d0", 85, 85, 900), ("#14b8a6", 60, 55, 700))),
    "meadow": ("green", _mesh("#1a2e05", ("#84cc16", 20, 30, 1100), ("#22c55e", 80, 80, 1000), ("#facc15", 65, 5, 700))),
    "slate": ("light", "linear-gradient(135deg, #e2e8f0 0%, #cbd5e1 55%, #b8c4d4 100%)"),
    "paper": ("light", _mesh("#f5f1ea", ("#e7dccb", 20, 20, 1100), ("#efe7da", 85, 80, 1000))),
    "cloud": ("light", _mesh("#eef2f7", ("#c7d7f0", 20, 25, 1100), ("#dde7f5", 85, 80, 1000), ("#e9e4f5", 60, 0, 800))),
    "peach": ("light", _mesh("#fdf2ec", ("#fbc4a8", 15, 20, 1100), ("#f9d5e5", 85, 75, 1000), ("#fde7c8", 55, 105, 900))),
}
CATEGORIES = sorted({c for c, _ in BACKGROUNDS.values()})
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")
# Fine grain over the wallpaper stops gradients from banding after H.264 encoding.
GRAIN = ("<svg xmlns='http://www.w3.org/2000/svg' width='100%' height='100%' style='position:absolute;inset:0;"
         "opacity:{o};mix-blend-mode:overlay'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' "
         "numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(#n)'/></svg>")
DRIFT = 0.06  # the wallpaper is this much larger than the canvas on each side, and pans within it


def pick_background(value, name: str) -> str:
    """A preset, a category (dark, blue, purple, orange, green, light), `auto` (any preset), or a
    list of presets: the choice comes from the video's name, so videos differ and re-renders match."""
    h = int(hashlib.sha1(str(name).encode()).hexdigest(), 16)
    if isinstance(value, (list, tuple)):
        pool = [str(v) for v in value]
    elif value == "auto":
        pool = sorted(BACKGROUNDS)
    elif value in CATEGORIES:
        pool = sorted(k for k, (c, _) in BACKGROUNDS.items() if c == value)
    else:
        return str(value)
    return pool[h % len(pool)] if pool else "aurora"


def _even(x: float) -> int:
    return max(2, int(round(x / 2)) * 2)


def _chrome_band(style) -> tuple[float, int, int]:
    cw, ch = style.canvas
    k = min(cw, ch) / 1080
    bar = _even(40 * k) if style.chrome else 0
    band = _even(118 * k) if getattr(style, "subtitles", False) else 0
    return k, bar, band


def auto_viewport(style) -> tuple[int, int]:
    """The viewport that fills the canvas at 1:1 (for `viewport: auto`)."""
    cw, ch = style.canvas
    _, bar, band = _chrome_band(style)
    pad = style.padding * min(cw, ch)
    return int(cw - 2 * pad) // 2 * 2, int(ch - 2 * pad - bar - band) // 2 * 2


MAX_FILL = 2.0  # fill: auto scales a small recording up this far at most


def layout(style, viewport: tuple[int, int]) -> dict:
    """Where the window and the recording go on the canvas."""
    cw, ch = style.canvas
    vw, vh = viewport
    k, bar, band = _chrome_band(style)
    pad = style.padding * min(cw, ch)
    s = min((cw - 2 * pad) / vw, (ch - 2 * pad - bar - band) / vh)
    fill = getattr(style, "fill", "auto")
    if fill is False:
        s = min(1.0, s)
    elif fill == "auto":
        s = min(MAX_FILL, s)
    if abs(s - 1.0) < 0.01:  # viewport: auto rounds to even pixels; keep it exactly 1:1
        s = 1.0
    w, h = max(2, int(vw * s) // 2 * 2), max(2, int(vh * s) // 2 * 2)  # round down: stay inside the padding
    x = _even((cw - w) / 2)
    wy = _even((ch - band - h - bar) / 2)
    return {"canvas": [cw, ch], "scale": round(s, 4), "w": w, "h": h, "x": x, "y": wy + bar,
            "bar": bar, "band": band, "win": [x, wy, w, h + bar], "radius": style.radius}


def fits_1to1(style, viewport: tuple[int, int]) -> tuple[int, int]:
    """The largest viewport (no wider or taller than this one) placed at 1:1 on this canvas."""
    fw, fh = auto_viewport(style)
    return min(viewport[0], fw), min(viewport[1], fh)


def _background_css(value: str, base_dir: Path) -> str:
    if value in BACKGROUNDS:
        return BACKGROUNDS[value][1]
    p = (base_dir / value) if not Path(value).is_absolute() else Path(value)
    if p.suffix.lower() in IMAGE_EXT and p.exists():
        mime = {".jpg": "jpeg", ".jpeg": "jpeg"}.get(p.suffix.lower(), p.suffix.lower()[1:])
        return f"url(data:image/{mime};base64,{base64.b64encode(p.read_bytes()).decode()}) center/cover no-repeat"
    return value  # a CSS colour or gradient


def _font_face() -> str:
    p = TEMPLATES / "fonts" / "mona-sans-var-latin.woff2"
    if not p.exists():
        return ""
    return ("@font-face{font-family:'DS Mona';font-weight:200 900;"
            f"src:url(data:font/woff2;base64,{base64.b64encode(p.read_bytes()).decode()}) format('woff2');}}")


def _corners(style) -> str:
    return "corner-shape:squircle;" if getattr(style, "corners", "round") == "squircle" else ""


def _radius(style) -> int:
    # a squircle needs a larger radius to look as soft as a round corner
    return int(style.radius * (1.8 if getattr(style, "corners", "round") == "squircle" else 1))


def wallpaper_html(style, lay: dict, base_dir: Path, bg: str) -> str:
    cw, ch = lay["canvas"]
    m = DRIFT if getattr(style, "motion", "none") == "drift" else 0
    w, h = _even(cw * (1 + 2 * m)), _even(ch * (1 + 2 * m))
    light = bg in BACKGROUNDS and BACKGROUNDS[bg][0] == "light"
    return (f"<!doctype html><html><body style='margin:0;width:{w}px;height:{h}px;position:relative;overflow:hidden;"
            f"background:{_background_css(bg, base_dir)}'>{GRAIN.format(o='.035' if light else '.07')}</body></html>")


def window_html(style, lay: dict) -> str:
    cw, ch = lay["canvas"]
    x, y, w, h = lay["win"]
    r, bar = _radius(style), lay["bar"]
    ring = "0 0 0 1.5px rgba(255,255,255,.34)" if getattr(style, "border", False) else "0 0 0 1px rgba(15,23,42,.10)"
    shadow = ", ".join([ring] + (["0 26px 70px rgba(2,6,23,.42)", "0 8px 22px rgba(2,6,23,.22)"] if style.shadow else []))
    chrome = ""
    if bar:
        d = bar * 0.3
        dots = "".join(f"<i style='width:{d}px;height:{d}px;border-radius:50%;background:{c};display:block'></i>"
                       for c in ("#ff5f57", "#febc2e", "#28c840"))
        title = html.escape(style.chrome_title or "")
        chrome = (f"<div style='position:absolute;inset:0 0 auto 0;height:{bar}px;display:flex;align-items:center;"
                  f"padding:0 {bar * 0.42}px;gap:{d * 0.75}px;background:#eef1f5;border-bottom:1px solid #dde2ea'>{dots}"
                  f"<span style='position:absolute;left:0;right:0;text-align:center;font:500 {bar * 0.34}px "
                  f"\"DS Mona\",system-ui,sans-serif;color:#475569'>{title}</span></div>")
    return (f"<!doctype html><html><head><style>{_font_face()}html,body{{margin:0;background:transparent}}</style></head>"
            f"<body style='width:{cw}px;height:{ch}px;position:relative;overflow:hidden'>"
            f"<div style='position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px;border-radius:{r}px;{_corners(style)}"
            f"overflow:hidden;background:#fff;box-shadow:{shadow}'>{chrome}</div></body></html>")


def mask_html(style, lay: dict) -> str:
    w, h, r = lay["w"], lay["h"], _radius(style)
    top = 0 if lay["bar"] else r
    return (f"<!doctype html><html><body style='margin:0;width:{w}px;height:{h}px;background:#000;overflow:hidden'>"
            f"<div style='width:{w}px;height:{h}px;background:#fff;border-radius:{top}px {top}px {r}px {r}px;{_corners(style)}'></div>"
            "</body></html>")


def frame_assets(style, viewport: tuple[int, int], base_dir: Path, name: str = "", log=print) -> dict:
    """Draw (or reuse from the cache) the wallpaper, window and mask. Returns the layout plus paths."""
    lay = layout(style, viewport)
    bg = pick_background(style.background, name)
    cw, ch = lay["canvas"]
    m = DRIFT if getattr(style, "motion", "none") == "drift" else 0
    pages = {"wallpaper.png": (wallpaper_html(style, lay, base_dir, bg), [_even(cw * (1 + 2 * m)), _even(ch * (1 + 2 * m))], False),
             "window.png": (window_html(style, lay), [cw, ch], True),
             "mask.png": (mask_html(style, lay), [lay["w"], lay["h"]], False)}
    key = hashlib.sha256(json.dumps([lay, {k: v[0] for k, v in pages.items()}]).encode()).hexdigest()[:16]
    d = cache_dir() / "frames" / key
    if not all((d / n).exists() for n in pages):
        d.mkdir(parents=True, exist_ok=True)
        from playwright.sync_api import sync_playwright
        from .tools import install_chromium
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch()
            except Exception as e:
                if "Executable doesn't exist" not in str(e):
                    raise
                install_chromium(log=log)
                browser = pw.chromium.launch()
            for fname, (doc, (w, h), transparent) in pages.items():
                page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
                page.set_content(doc, wait_until="load")
                page.wait_for_timeout(100)
                page.screenshot(path=str(d / fname), omit_background=transparent)
                page.close()
            browser.close()
    return {**lay, "background": bg, "motion": getattr(style, "motion", "none"),
            "wallpaper": str(d / "wallpaper.png"), "window": str(d / "window.png"), "mask": str(d / "mask.png")}


def filter_graph(lay: dict, fps: int) -> str:
    """Inputs: 0 frames, 2 wallpaper, 3 window layer, 4 mask (all looped). Output label [base]."""
    cw, ch = lay["canvas"]
    w, h, x, y = lay["w"], lay["h"], lay["x"], lay["y"]
    if lay.get("motion") == "drift":
        ax, ay = int(cw * DRIFT * 0.9), int(ch * DRIFT * 0.9)
        cx = f"(iw-{cw})/2+{ax}*sin(2*PI*t/23)"
        cy = f"(ih-{ch})/2+{ay}*sin(2*PI*t/31+1.3)"
    else:
        cx, cy = f"(iw-{cw})/2", f"(ih-{ch})/2"
    return (f"[2:v]crop=w={cw}:h={ch}:x='{cx}':y='{cy}',format=rgba[wall];"
            f"[3:v]format=rgba[shell];[wall][shell]overlay=0:0[bg];"
            f"[0:v]fps={fps},scale={w}:{h}:flags=lanczos,format=rgba[rec];"
            f"[4:v]format=gray,scale={w}:{h}[m];[rec][m]alphamerge[win];"
            f"[bg][win]overlay={x}:{y}:shortest=1[base]")
