"""Drive the app with Playwright and capture frames with timestamps.

Frames come from the page screencast (JPEG, full viewport size) with the browser's own
timestamps, so the assembler can rebuild exact timing, including sped-up waits.
"""
from __future__ import annotations

import asyncio
import base64
import json
import shutil
import time
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PWTimeout

from . import config, session
from .config import CURSOR_MOVE, LEAD_IN, SLIDE_MIN, TAIL, TEMPLATES, ZOOM_MS
from .tools import launch_chromium

# Always masked, in both modes (docs/modes-and-privacy.md). The storyboard can add more.
DEFAULT_REDACT_SELECTORS = [
    "input[type=password]",
    "[data-secret]",
    "input[name*=secret i]",
    "input[name*=token i]",
    "input[name*=apikey i]",
    "input[name*=api_key i]",
    "input[autocomplete=cc-number]",
    "input[autocomplete=cc-csc]",
]
DEFAULT_REDACT_PATTERNS = [
    r"\bsk-[A-Za-z0-9_-]{8,}",                       # OpenAI / Anthropic style keys
    r"\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{8,}",  # Stripe
    r"\bAKIA[0-9A-Z]{16}\b",                         # AWS access key id
    r"\bgh[pousr]_[A-Za-z0-9]{20,}",                 # GitHub tokens
    r"\bgithub_pat_[A-Za-z0-9_]{20,}",
    r"\bxox[abprs]-[A-Za-z0-9-]{10,}",               # Slack
    r"\bAIza[0-9A-Za-z_-]{30,}",                     # Google API key
    r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",  # JWT
    r"\b[A-Fa-f0-9]{32,}\b",                         # long hex secrets
    r"\b(?:\d[ -]?){13,19}\b",                       # card numbers
    r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}\b",      # IBAN
    r"https?://\S*(?:hooks\.slack\.com|/webhook|/hooks/)\S*",  # webhook URLs
    r"[?&](?:token|key|secret|sig|signature|apikey|api_key|access_token)=[^&\s]{6,}",
]

FONT_DIR = TEMPLATES / "fonts"


# (family, file, weight range, width range): variable fonts, SIL OFL (templates/fonts/OFL-*.txt).
FONTS = [
    ("DS Inter", "inter-var-latin.woff2", "100 900", None),
    ("DS Archivo", "archivo-var-latin.woff2", "100 900", "62% 125%"),
    ("DS Mona", "mona-sans-var-latin.woff2", "200 900", "75% 125%"),
    ("DS Mono", "jetbrains-mono-var-latin.woff2", "100 800", None),
]


def _font_faces() -> str:
    """The overlay's fonts as data URLs, so slides and captions look the same on every machine."""
    out = []
    for family, name, weight, stretch in FONTS:
        p = FONT_DIR / name
        if not p.exists():
            continue
        b64 = base64.b64encode(p.read_bytes()).decode()
        out.append(f"@font-face{{font-family:'{family}';font-style:normal;font-weight:{weight};"
                   + (f"font-stretch:{stretch};" if stretch else "")
                   + f"font-display:block;src:url(data:font/woff2;base64,{b64}) format('woff2');}}")
    return "".join(out)


def init_script(sb) -> str:
    cfg = {
        "css": (TEMPLATES / "titles" / "overlay.css").read_text(encoding="utf-8"),
        "fontFaces": _font_faces(),
        "redactSelectors": DEFAULT_REDACT_SELECTORS + sb.redact_selectors,
        "redactPatterns": DEFAULT_REDACT_PATTERNS + sb.redact_patterns,
        "theme": sb.style.theme,
        "captionStyle": sb.style.captions,
        "accent": sb.style.accent,
    }
    js = (Path(__file__).parent / "overlay.js").read_text(encoding="utf-8")
    return f"const CFG = {json.dumps(cfg)};\n{js}"


class SessionExpired(Exception):
    pass


class Recorder:
    def __init__(self, sb, narr: dict, out: Path, headless: bool = True, log=print):
        self.sb, self.narr, self.out, self.headless, self.log = sb, narr, out, headless, log
        self.frames: list[tuple[float, int, float]] = []   # (browser ts, index, arrival time)
        self.marks: list[dict] = []
        self.waits: list[dict] = []
        self.strings: list[dict] = []
        self.masked: list[dict] = []
        self.fdir = out / "frames"
        self.page = None
        self.current_route = None
        self.zoomed = False

    # -- frames -----------------------------------------------------------
    def _on_frame(self, f) -> None:
        data = f["data"] if isinstance(f, dict) else f.data
        ts = float(f["timestamp"] if isinstance(f, dict) else f.timestamp)
        if ts > 1e11:  # Playwright reports epoch milliseconds
            ts /= 1000.0
        idx = len(self.frames)
        (self.fdir / f"{idx:06d}.jpg").write_bytes(data)
        self.frames.append((float(ts), idx, time.time()))

    # -- helpers ----------------------------------------------------------
    async def ds(self, expr: str, arg=None):
        return await self.page.evaluate(f"(a) => window.__ds.{expr}", arg)

    async def navigate(self, route: str) -> None:
        url = route if route.startswith("http") else self.sb.base_url + route
        if self.current_route is not None:
            await self.ds("captionHide()")  # the old caption must not sit on the new page
        if self.sb.navigation == "spa" and self.current_route is not None:
            await self.page.evaluate(
                "(r) => { history.pushState({}, '', r); window.dispatchEvent(new PopStateEvent('popstate', {state: {}})); }",
                route,
            )
            await self.page.wait_for_timeout(120)
        else:
            await self.page.goto(url, wait_until="domcontentloaded")
            self.zoomed = False  # a new document starts unzoomed
            try:
                await self.page.wait_for_load_state("networkidle", timeout=12000)
            except PWTimeout:
                pass
        self.current_route = route
        if self.sb.auth:
            await self.check_session()

    async def check_session(self) -> None:
        if await self.page.locator("input[type=password]").count() > 0:
            raise SessionExpired(
                f"A sign-in form is showing. The saved session for {self.sb.auth!r} has expired or is missing: "
                f"the account owner runs `studio login {self.sb.auth}` again."
            )

    async def hold_until(self, t_start: float, need: float) -> None:
        """Wait until the step has lasted `need` seconds of OUTPUT time (sped-up waits count less)."""
        while True:
            elapsed = time.time() - t_start
            saved = sum((min(w["end"], time.time()) - max(w["start"], t_start)) * (1 - 1 / w["factor"])
                        for w in self.waits if w["end"] > t_start)
            left = need - (elapsed - saved)
            if left <= 0:
                return
            await self.page.wait_for_timeout(min(left, 0.5) * 1000)

    async def collect(self, where: str) -> None:
        try:
            s = await self.ds("collect()")
            s["where"] = where
            s["url"] = self.page.url
            self.strings.append(s)
            for m in await self.ds("masked()"):
                m["where"] = where
                self.masked.append(m)
        except Exception as e:  # navigation in flight; the next collect catches up
            self.log(f"  collect skipped at {where}: {e}")

    async def sped_up_wait(self, step, selector: str) -> None:
        await self.ds("badge(a)", f"Sped up {step.speed_factor:g}x" if step.speed_up else None)
        w = {"step": step.id, "start": time.time(), "end": None, "factor": step.speed_factor if step.speed_up else 1.0}
        if step.speed_up:
            self.waits.append(w)
        try:
            await self.page.locator(selector).first.wait_for(state="visible", timeout=step.timeout * 1000)
        finally:
            w["end"] = time.time()
            if step.speed_up:
                await self.ds("badge(a)", None)

    async def zoom_to(self, loc, scale: float) -> None:
        await loc.wait_for(state="visible", timeout=15000)
        s = await loc.evaluate("(e, a) => window.__ds.zoomTo(e, a[0], a[1])", [scale, ZOOM_MS])
        self.zoomed = s > 1

    async def zoom_out(self) -> None:
        if self.zoomed:
            await self.ds(f"zoomOut({ZOOM_MS})")
            self.zoomed = False

    async def point_and(self, loc, action: str, text: str | None = None, zoom: float = 0, zoom_loc=None) -> None:
        await loc.wait_for(state="visible", timeout=15000)
        await loc.scroll_into_view_if_needed()
        if zoom:
            await self.zoom_to(zoom_loc or loc, zoom)  # before the cursor moves, so it lands on the zoomed spot
        await self.ds("cursorShow(true)")
        await loc.evaluate("(e) => window.__ds.ringEl(e)")
        await loc.evaluate(f"(e) => window.__ds.cursorToEl(e, {int(CURSOR_MOVE * 1000)})")
        await loc.hover()
        await self.page.wait_for_timeout(180)
        if action == "hover":
            return
        await self.ds("clickPulse()")
        await loc.click()
        if action == "type" and text is not None:
            await loc.press_sequentially(text, delay=55)
        await self.page.wait_for_timeout(300)

    # -- main -------------------------------------------------------------
    async def run(self) -> dict:
        sb = self.sb
        if self.fdir.exists():
            shutil.rmtree(self.fdir)
        self.fdir.mkdir(parents=True)
        storage = None
        if sb.auth:
            storage = config.auth_dir() / f"{sb.auth}.json"
            if not storage.exists():
                raise SessionExpired(f"No saved session {sb.auth!r}: the account owner runs `studio login {sb.auth}` first.")
        w, h = sb.viewport
        async with async_playwright() as pw:
            browser = await launch_chromium(
                pw, headless=self.headless, log=self.log,
                args=["--hide-scrollbars", "--force-color-profile=srgb", "--disable-features=Translate"],
            )
            ctx = await browser.new_context(
                viewport={"width": w, "height": h}, device_scale_factor=1, bypass_csp=True,
                locale="en-US", color_scheme="light",
                storage_state=str(storage) if storage else None,
            )
            await ctx.add_init_script(script=init_script(sb))
            self.page = page = await ctx.new_page()
            page.set_default_timeout(30000)

            first_route = next((s.route for s in sb.steps if s.route), "/")
            await self.navigate(first_route)
            await page.wait_for_timeout(400)
            # The intro slide is already up when the first frame is captured.
            intro_layout, self.outro_layout = sb.layouts()
            intro = {"kind": "intro", "layout": intro_layout, "eyebrow": sb.eyebrow, "title": sb.title,
                     "note": sb.intro_note or "", "count": len(sb.steps), "steps": [s.caption.title for s in sb.steps]}
            if intro_layout == "product":  # the app's first screen, masked like every frame
                await page.wait_for_timeout(500)
                shot = await page.screenshot(type="jpeg", quality=85)
                intro.update(shot="data:image/jpeg;base64," + base64.b64encode(shot).decode(), shotRatio=round(w / h, 4))
            await page.evaluate("(s) => { window.__ds.reset(); }")
            await self.ds("slide(a)", intro)
            await page.wait_for_timeout(300)
            await page.screencast.start(on_frame=self._on_frame, quality=92, size={"width": w, "height": h})
            await page.wait_for_timeout(250)
            t_rec = time.time()

            # intro
            t0 = time.time()
            n = self.narr.get("_intro", {}).get("seconds", 0)
            await self.hold_until(t0, max(SLIDE_MIN, LEAD_IN + n + TAIL) if n else SLIDE_MIN)
            await self.collect("intro")
            self.marks.append({"id": "_intro", "kind": "slide", "start": t0, "end": time.time()})
            await self.ds("slide(a)", None)

            for step in sb.steps:
                t_start = time.time()
                self.log(f"  step {step.caption.n} {step.id}")
                await self.ds("ringOff()")
                new_page = bool(step.route and step.route != self.current_route)
                if self.zoomed and (not step.zoom or new_page):
                    await self.zoom_out()
                if new_page:
                    await self.navigate(step.route)
                await self.ds("caption(a)", {"n": step.caption.n, "total": len(sb.steps),
                                             "title": step.caption.title, "sub": step.caption.sub})
                if step.highlight:
                    hl = page.locator(step.highlight).first
                    await hl.wait_for(state="visible", timeout=step.timeout * 1000)
                    await hl.evaluate("(e) => window.__ds.ringEl(e, 8)")

                zoom_sel = step.zoom_on or step.target or step.highlight
                zoom_loc = page.locator(zoom_sel).first if step.zoom and zoom_sel else None
                if step.action == "wait_for":
                    await self.sped_up_wait(step, step.target)
                elif step.action in ("click", "type", "hover"):
                    await self.point_and(page.locator(step.target).first, step.action, step.text,
                                         zoom=step.zoom, zoom_loc=zoom_loc)
                elif step.action == "scroll":
                    if step.target:
                        await page.locator(step.target).first.evaluate("(e) => e.scrollIntoView({behavior: 'smooth', block: 'center'})")
                    else:
                        await page.evaluate("(d) => window.scrollBy({top: d, behavior: 'smooth'})", step.scroll_by or 500)
                    await page.wait_for_timeout(900)
                elif step.action == "goto":
                    pass  # the route above did it
                if step.wait_for:
                    await self.sped_up_wait(step, step.wait_for)
                if zoom_loc is not None and step.action not in ("click", "type", "hover"):
                    await self.zoom_to(zoom_loc, step.zoom)

                n = self.narr[step.id]["seconds"]
                await self.hold_until(t_start, LEAD_IN + n + TAIL + step.hold)
                await self.collect(step.id)
                self.marks.append({"id": step.id, "kind": "step", "start": t_start, "end": time.time()})

            # outro
            t0 = time.time()
            await self.zoom_out()
            await self.ds("ringOff()")
            await self.ds("captionOff()")
            await self.ds("cursorShow(false)")
            outro = {"kind": "outro", "layout": self.outro_layout, "eyebrow": sb.eyebrow, "heading": sb.outro_heading,
                     "bullets": sb.outro_bullets, "cta": sb.outro_cta}
            await self.ds("slide(a)", outro)
            n = self.narr.get("_outro", {}).get("seconds", 0)
            await self.hold_until(t0, max(SLIDE_MIN + 1.0, LEAD_IN + n + TAIL + 0.6))
            await self.collect("outro")
            t_end = time.time()
            self.marks.append({"id": "_outro", "kind": "slide", "start": t0, "end": t_end})
            await page.wait_for_timeout(200)
            await page.screencast.stop()
            if storage:
                # Supabase-style apps rotate refresh tokens while we record; write the refreshed
                # session back so the next render still works. Only cookies and auth entries are
                # kept (studio/session.py). The file is never printed.
                session.write_back(await ctx.storage_state(indexed_db=True), storage, log=self.log)
            await ctx.close()
            await browser.close()

        if not self.frames:
            raise RuntimeError("no frames were captured")
        # Map browser frame timestamps onto the wall clock used for the marks.
        offset = min(arr - ts for ts, _, arr in self.frames)
        if abs(offset) > 5:
            raise RuntimeError(f"frame clock is {offset:.1f}s away from the wall clock; check the timestamp unit")
        frames = [[round(ts + offset, 4), idx] for ts, idx, _ in self.frames]
        timeline = {
            "storyboard": str(Path(sb.path).resolve()), "name": sb.name, "mode": sb.mode, "variant": sb.variant,
            "viewport": list(sb.viewport), "recorded_at": t_rec,
            "start": frames[0][0], "end": t_end,
            "marks": self.marks, "waits": self.waits, "frames": frames,
            "clock_offset": offset,
        }
        return timeline


def record(sb, narr: dict, out: Path, headless: bool = True, log=print) -> tuple[dict, list, list]:
    rec = Recorder(sb, narr, out, headless=headless, log=log)
    timeline = asyncio.run(rec.run())
    return timeline, rec.strings, rec.masked
