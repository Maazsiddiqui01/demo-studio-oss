"""`studio slides <storyboard>`: stills of every intro layout, outro layout and caption style,
drawn over the storyboard's own app, so you can pick a look before rendering."""
from __future__ import annotations

import asyncio
import base64
from pathlib import Path

from .record import init_script
from .serve import serving
from .storyboard import CAPTIONS, INTRO_LAYOUTS, OUTRO_LAYOUTS
from .tools import launch_chromium


async def _run(sb, dest: Path, log=print) -> list[Path]:
    from playwright.async_api import async_playwright
    w, h = sb.viewport
    shots: list[Path] = []
    async with async_playwright() as pw:
        browser = await launch_chromium(pw, log=log, args=["--hide-scrollbars", "--force-color-profile=srgb"])
        ctx = await browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, bypass_csp=True,
                                        locale="en-US", color_scheme="light")
        await ctx.add_init_script(script=init_script(sb))
        page = await ctx.new_page()
        first = next((s.route for s in sb.steps if s.route), "/")
        await page.goto(first if first.startswith("http") else sb.base_url + first, wait_until="domcontentloaded")
        try:
            await page.wait_for_load_state("networkidle", timeout=12000)
        except Exception:
            pass
        await page.wait_for_timeout(600)
        app = base64.b64encode(await page.screenshot(type="jpeg", quality=85)).decode()

        async def snap(name: str) -> None:
            await page.wait_for_timeout(1500)  # let the entrance animations finish
            p = dest / f"{name}.png"
            await page.screenshot(path=str(p))
            shots.append(p)

        base = {"eyebrow": sb.eyebrow, "count": len(sb.steps), "steps": [s.caption.title for s in sb.steps]}
        for layout in INTRO_LAYOUTS:
            await page.evaluate("(s) => window.__ds.slide(s)", {**base, "kind": "intro", "layout": layout, "title": sb.title,
                                                                "note": sb.intro_note or "", "shot": f"data:image/jpeg;base64,{app}",
                                                                "shotRatio": round(w / h, 4)})
            await snap(f"intro-{layout}")
        for layout in OUTRO_LAYOUTS:
            await page.evaluate("(s) => window.__ds.slide(s)", {**base, "kind": "outro", "layout": layout,
                                                                "heading": sb.outro_heading, "bullets": sb.outro_bullets,
                                                                "cta": sb.outro_cta or ("github.com/you/your-app" if layout == "cta" else None)})
            await snap(f"outro-{layout}")
        await page.evaluate("() => window.__ds.slide(null)")
        st = sb.steps[min(1, len(sb.steps) - 1)]
        for style in CAPTIONS:
            await page.evaluate("(c) => { const r = document.querySelector('ds-overlay').shadowRoot; r.getElementById('cap').className = 'cap ' + c; }", style)
            await page.evaluate("(c) => window.__ds.captionOff()")
            await page.evaluate("(c) => window.__ds.caption(c)", {"n": st.caption.n, "total": len(sb.steps),
                                                                "title": st.caption.title, "sub": st.caption.sub})
            await snap(f"caption-{style}")
        await browser.close()
    return shots


def slides(sb, dest: Path, log=print) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    with serving(sb):
        return asyncio.run(_run(sb, dest, log=log))


def backgrounds(dest: Path, log=print) -> Path:
    """One image with every wallpaper preset, labelled by name and category."""
    from playwright.sync_api import sync_playwright
    from .style import BACKGROUNDS, CATEGORIES
    tiles = []
    for cat in CATEGORIES:
        for name, (c, css) in sorted(BACKGROUNDS.items()):
            if c == cat:
                tiles.append(f"<figure><div class='t'><div style='width:1920px;height:1080px;zoom:.1311;background:{css}'></div></div>"
                             f"<figcaption><b>{name}</b> {cat}</figcaption></figure>")
    page_html = ("<!doctype html><html><body style='margin:0;padding:28px;background:#0b1618;font:15px system-ui,sans-serif;"
                 "color:#e8f1f0;display:grid;grid-template-columns:repeat(6,1fr);gap:18px;width:1600px'>"
                 "<style>figure{margin:0}.t{aspect-ratio:16/9;border-radius:10px;overflow:hidden;box-shadow:0 0 0 1px rgba(255,255,255,.1)}"
                 "figcaption{margin-top:7px;color:#9db3b3}figcaption b{color:#e8f1f0;margin-right:6px}</style>"
                 + "".join(tiles) + "</body></html>")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1656, "height": 600})
        pg.set_content(page_html)
        pg.screenshot(path=str(dest), full_page=True)
        b.close()
    log(f"{len(tiles)} wallpapers in {dest}. Use one with style.background: <name>, a category "
        f"({', '.join(CATEGORIES)}), a list of names, or auto (picked per video from its name).")
    return dest
