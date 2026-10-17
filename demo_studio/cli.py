"""studio: storyboard in, narrated walkthrough video out.

  studio init     [folder]    (a starter storyboard and a tiny demo app that renders as is)
  studio doctor               (checks ffmpeg, the browser, the voice and the GPU)
  studio validate <storyboard.yaml>
  studio slides   <storyboard.yaml>   (stills of every intro, outro and caption design over your app)
  studio backgrounds [--out file.png] (a gallery of every wallpaper preset)
  studio render   <storyboard.yaml> [--headed] [--keep-frames] [--no-cut] [--cut-only]
  studio check    <out-dir> [--frames pass|fail --note "..."] [--cost "..."]
  studio login    <name>      (you sign in yourself; the session is saved outside the repo)
  studio logout   <name>      (deletes that saved session)
  studio publish  <out-dir>   (a folder or your server, per demo-studio.yaml; see docs/publishing.md)
  studio serve    <folder> [--port 5173]   (preview a demo app with client-side routes)
  studio expire               (on the server: removes private links past their expiry date)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from . import __version__, config
from .storyboard import StoryboardError, load


def log(msg: str) -> None:
    print(msg, flush=True)


def _storyboard_for_out(out: Path):
    tl = json.loads((out / "timeline.json").read_text(encoding="utf-8"))
    sb = load(tl["storyboard"], variant=tl.get("variant"))
    if tl["name"] != sb.name and sb.cutdown:
        cut = sb.derive_cutdown()
        if cut.name == tl["name"]:
            sb = cut
    return sb


def cmd_validate(a) -> int:
    try:
        sb = load(a.storyboard, variant=a.variant)
    except StoryboardError as e:
        log("INVALID:")
        for err in e.errors:
            log(f"  - {err}")
        return 2
    log(f"OK: {sb.name} ({sb.mode}), {len(sb.steps)} steps, voice {sb.voice}")
    for w in sb.warnings:
        log(f"  warning: {w}")
    if sb.cutdown:
        cut = sb.derive_cutdown()
        log(f"  cut-down: {cut.name}, steps {[s.id for s in cut.steps]}")
    for v in (sb.raw.get("variants") or {}) if not a.variant else []:
        try:
            vs = load(a.storyboard, variant=v)
            log(f"  variant {v}: {vs.name}, viewport {vs.viewport[0]}x{vs.viewport[1]}, canvas {vs.style.canvas[0]}x{vs.style.canvas[1]}")
        except StoryboardError as e:
            log(f"  variant {v}: INVALID: {'; '.join(e.errors)}")
            return 2
    if sb.style.frame:
        from .style import pick_background
        log(f"  framed: background {pick_background(sb.style.background, sb.name)}, viewport {sb.viewport[0]}x{sb.viewport[1]}")
    return 0


def render_one(sb, a) -> dict:
    from . import tts
    from .assemble import assemble
    from .record import record

    out = config.out_dir_for(sb)
    out.mkdir(parents=True, exist_ok=True)
    # a new render needs a new frame review and a new publish
    for stale in (out / "qa" / "frames_verdict.json", out / "delivery.json"):
        stale.unlink(missing_ok=True)
    if sb.mode == "handover" and not sb.local_copy:
        log(f"[{sb.name}] handover mode: real data, private output under {out}")
    t = time.time()
    if getattr(a, "reassemble", False):
        # encode again from the recording already on disk (kept after a failed encode, or by --keep-frames)
        need = [out / "timeline.json", out / "narration.json", out / "frames"]
        missing = [x.name for x in need if not x.exists()]
        if missing:
            raise SystemExit(f"[{sb.name}] --reassemble needs a kept recording in {out}; missing: {', '.join(missing)}")
        narr = json.loads((out / "narration.json").read_text(encoding="utf-8"))
        timeline = json.loads((out / "timeline.json").read_text(encoding="utf-8"))
        if timeline.get("viewport"):
            sb.viewport = tuple(timeline["viewport"])
        log(f"[{sb.name}] reassemble: {len(timeline['frames'])} recorded frames")
        info = assemble(sb, timeline, narr, out, keep_frames=a.keep_frames, log=log)
        return _gate_and_report(sb, a, out, info, t)
    log(f"[{sb.name}] narrate: {len(sb.narration_lines())} lines, voice {sb.voice}, backend {tts.backend()} on {tts.device()}")
    narr = tts.narrate(sb, out / "audio")
    (out / "narration.json").write_text(json.dumps(narr, indent=2), encoding="utf-8")
    if sb.driver == "desktop":
        from .desktop import record_desktop
        log(f"[{sb.name}] record: the desktop window matching {sb.app.get('window')!r}")
        timeline, strings, masked = record_desktop(sb, narr, out, log=log)
        sb.viewport = tuple(timeline["viewport"])  # the window's size is the recording's size
    else:
        log(f"[{sb.name}] record: {sb.base_url} at {sb.viewport[0]}x{sb.viewport[1]}")
        from .serve import serving
        with serving(sb):
            timeline, strings, masked = record(sb, narr, out, headless=not a.headed, log=log)
    (out / "timeline.json").write_text(json.dumps(timeline), encoding="utf-8")
    (out / "strings.json").write_text(json.dumps(strings, indent=1), encoding="utf-8")
    (out / "masked.json").write_text(json.dumps(masked, indent=1), encoding="utf-8")
    log(f"[{sb.name}] assemble: {len(timeline['frames'])} frames")
    info = assemble(sb, timeline, narr, out, keep_frames=a.keep_frames, log=log)
    if sb.mode == "handover":
        ret = out.parent / "RETENTION.md"
        if not ret.exists():
            ret.write_text(
                f"# Retention: {sb.client}\n\n- Rendered: {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC\n"
                "- Contains the client's real data. Private: for this client only.\n"
                "- Received by: (fill in when you deliver it)\n- The owner decides when it is deleted.\n",
                encoding="utf-8")
    return _gate_and_report(sb, a, out, info, t)


def _gate_and_report(sb, a, out, info: dict, t: float) -> dict:
    from .gate import run_checks
    log(f"[{sb.name}] gate")
    res = run_checks(sb, out, cost=a.cost, speech=not a.no_speech)
    log(f"[{sb.name}] done in {time.time() - t:.0f}s: {info['total']:.1f}s video at {out / 'video.mp4'}")
    _print_gate(res)
    return res


def _print_gate(res: dict) -> None:
    for k in ("frames", "text", "audio", "file", "delivery", "vps"):
        ok = res[k]["ok"]
        log(f"  {k:9s} {'PASS' if ok is True else 'FAIL' if ok is False else 'PENDING'}")
    if res["text"]["hits"]:
        for h in res["text"]["hits"][:20]:
            log(f"    text: {h}")
    for k in ("timing_issues", "long_silences"):
        for x in res["audio"][k]:
            log(f"    audio: {x}")
    sp = res["audio"].get("speech") or {}
    if sp.get("similarity") is not None:
        log(f"    speech similarity {sp['similarity']}")


def cmd_render(a) -> int:
    try:
        sb = load(a.storyboard, variant=a.variant)
    except StoryboardError as e:
        log("INVALID storyboard, nothing rendered:")
        for err in e.errors:
            log(f"  - {err}")
        return 2
    for w in sb.warnings:
        log(f"  warning: {w}")
    if not a.cut_only:
        render_one(sb, a)
    if sb.cutdown and not a.no_cut:
        render_one(sb.derive_cutdown(), a)
    return 0


def cmd_check(a) -> int:
    from .gate import run_checks
    out = Path(a.out).resolve()
    sb = _storyboard_for_out(out)
    verdict = {"verdict": a.frames, "note": a.note or "", "at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")} if a.frames else None
    res = run_checks(sb, out, cost=a.cost, frames_verdict=verdict, speech=not a.no_speech)
    _print_gate(res)
    log(f"report: {out / 'REPORT.md'}")
    return 0 if res["passed"] else 1


def _find_login_url(name: str) -> str | None:
    import yaml
    h = config.home()
    for p in sorted(list(h.glob("*.y*ml")) + list((h / "storyboards").glob("*.y*ml"))):
        try:
            d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if d.get("auth") == name:
            return d.get("login_url") or d.get("base_url")
    return None


def cmd_login(a) -> int:
    import asyncio
    from playwright.async_api import async_playwright
    from .tools import launch_chromium

    url = a.url or _find_login_url(a.name)
    if not url or url.startswith("TODO"):
        log(f"No storyboard has auth: {a.name} with a base_url or login_url. Pass --url.")
        return 2
    dest_dir = config.auth_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{a.name}.json"

    async def run() -> None:
        async with async_playwright() as pw:
            browser = await launch_chromium(pw, headless=False, log=log)
            ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, locale="en-US")
            page = await ctx.new_page()
            await page.goto(url)
            log("")
            log(f"A browser window is open at {url}")
            log("Sign in there yourself (including any 2FA) and wait until the app's home screen shows.")
            log("The session is saved by itself once you are signed in (or press Enter here to save now).")
            log("Nothing you type in the browser is read by demo-studio.")
            closed = asyncio.get_running_loop().create_future()
            page.on("close", lambda _: closed.done() or closed.set_result(True))
            loop = asyncio.get_running_loop()
            enter = loop.create_future()

            def wait_enter() -> None:  # a daemon thread, so an unpressed Enter never blocks exit
                try:
                    input()
                except EOFError:
                    return
                loop.call_soon_threadsafe(lambda: enter.done() or enter.set_result(True))

            if sys.stdin and sys.stdin.isatty():
                threading.Thread(target=wait_enter, daemon=True).start()

            async def signed_in() -> None:
                """Signed in = off the login page, no password field, for three checks in a row."""
                login_path = urlparse(url).path.rstrip("/")
                ok = 0
                while True:
                    await asyncio.sleep(2)
                    try:
                        here = urlparse(page.url)
                        on_login = login_path and here.path.rstrip("/") == login_path
                        pw_field = await page.locator("input[type=password]").count()
                        ok = ok + 1 if (not on_login and pw_field == 0 and here.scheme.startswith("http")) else 0
                    except Exception:
                        ok = 0
                    if ok >= 3:
                        await asyncio.sleep(2)  # let the app finish writing its session
                        return

            auto = asyncio.ensure_future(signed_in())
            await asyncio.wait([enter, closed, auto], return_when=asyncio.FIRST_COMPLETED)
            if auto.done():
                log("Signed in: saving the session.")
            auto.cancel()
            await ctx.storage_state(path=str(dest), indexed_db=True)
            await browser.close()

    asyncio.run(run())
    if sys.platform == "win32":
        import getpass
        subprocess.run(["icacls", str(dest), "/inheritance:r", "/grant:r", f"{getpass.getuser()}:F"],
                       capture_output=True)
    if sys.platform == "win32":
        log(f"Saved the session for {a.name!r} to {dest} (readable by your Windows user only).")
    else:
        os.chmod(dest, 0o600)
        log(f"Saved the session for {a.name!r} to {dest} (readable by you only).")
    log("It is never committed or uploaded. Run `studio logout " + a.name + "` when the handover is done.")
    return 0


def cmd_logout(a) -> int:
    dest = config.auth_dir() / f"{a.name}.json"
    if dest.exists():
        dest.unlink()
        log(f"Deleted the saved session {a.name!r}.")
    else:
        log(f"No saved session {a.name!r}.")
    return 0


def cmd_publish(a) -> int:
    from .publish import publish
    out = Path(a.out).resolve()
    sb = _storyboard_for_out(out)
    res = publish(sb, out, log=log)
    log(json.dumps(res, indent=2))
    return 0 if res.get("ok") else 1


def cmd_serve(a) -> int:
    from .serve import serve_forever
    serve_forever(a.folder, a.port)
    return 0


def cmd_expire(a) -> int:
    from .expire import expire
    return expire(dry_run=a.dry_run)


def cmd_init(a) -> int:
    from .scaffold import init
    return init(Path(a.folder), force=a.force, log=log)


def cmd_slides(a) -> int:
    from .preview import slides
    try:
        sb = load(a.storyboard, variant=a.variant)
    except StoryboardError as e:
        log("INVALID storyboard:")
        for err in e.errors:
            log(f"  - {err}")
        return 2
    dest = Path(a.out) if a.out else config.out_dir_for(sb) / "slides"
    shots = slides(sb, dest, log=log)
    log(f"{len(shots)} stills in {dest}: " + ", ".join(p.stem for p in shots))
    log("Pick one with intro.layout, outro.layout and style.captions (and style.theme) in the storyboard.")
    return 0


def cmd_windows(a) -> int:
    from .desktop import list_windows
    for w in list_windows():
        x, y, ww, hh = w["rect"]
        log(f"{w['title']}   ({ww}x{hh} at {x},{y})")
    return 0


def cmd_inspect(a) -> int:
    from .desktop import inspect
    inspect(a.window, depth=a.depth, limit=a.limit, log=log)
    return 0


def cmd_backgrounds(a) -> int:
    from .preview import backgrounds
    backgrounds(Path(a.out), log=log)
    return 0


def cmd_doctor(a) -> int:
    from .doctor import doctor
    return doctor(log=log, download=a.download)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="studio", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"demo-studio {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init"); s.add_argument("folder", nargs="?", default=".")
    s.add_argument("--force", action="store_true", help="overwrite existing starter files"); s.set_defaults(fn=cmd_init)
    s = sub.add_parser("doctor"); s.add_argument("--download", action="store_true",
                                                 help="also download the browser and voice model now")
    s.set_defaults(fn=cmd_doctor)
    s = sub.add_parser("validate"); s.add_argument("storyboard"); s.add_argument("--variant")
    s.set_defaults(fn=cmd_validate)
    s = sub.add_parser("render"); s.add_argument("storyboard")
    s.add_argument("--variant", help="render one entry of the storyboard's variants: block")
    s.add_argument("--headed", action="store_true"); s.add_argument("--keep-frames", action="store_true")
    s.add_argument("--no-cut", action="store_true"); s.add_argument("--cut-only", action="store_true")
    s.add_argument("--no-speech", action="store_true", help="skip the faster-whisper check")
    s.add_argument("--reassemble", action="store_true",
                   help="encode again from the kept recording (frames/, timeline.json) without recording")
    s.add_argument("--cost", default=None); s.set_defaults(fn=cmd_render)
    s = sub.add_parser("slides", help="stills of every intro, outro and caption design over your app")
    s.add_argument("storyboard"); s.add_argument("--variant"); s.add_argument("--out"); s.set_defaults(fn=cmd_slides)
    s = sub.add_parser("windows", help="desktop driver: list the open windows")
    s.set_defaults(fn=cmd_windows)
    s = sub.add_parser("inspect", help="desktop driver: list a window's controls with selectors")
    s.add_argument("window", help="a regular expression matching the window title")
    s.add_argument("--depth", type=int, default=6); s.add_argument("--limit", type=int, default=400)
    s.set_defaults(fn=cmd_inspect)
    s = sub.add_parser("backgrounds", help="a gallery of every wallpaper preset")
    s.add_argument("--out", default="backgrounds.png"); s.set_defaults(fn=cmd_backgrounds)
    s = sub.add_parser("check"); s.add_argument("out")
    s.add_argument("--frames", choices=["pass", "fail"]); s.add_argument("--note")
    s.add_argument("--cost"); s.add_argument("--no-speech", action="store_true"); s.set_defaults(fn=cmd_check)
    s = sub.add_parser("login"); s.add_argument("name"); s.add_argument("--url"); s.set_defaults(fn=cmd_login)
    s = sub.add_parser("logout"); s.add_argument("name"); s.set_defaults(fn=cmd_logout)
    s = sub.add_parser("publish"); s.add_argument("out"); s.set_defaults(fn=cmd_publish)
    s = sub.add_parser("serve"); s.add_argument("folder"); s.add_argument("--port", type=int, default=5173)
    s.set_defaults(fn=cmd_serve)
    s = sub.add_parser("expire"); s.add_argument("--dry-run", action="store_true"); s.set_defaults(fn=cmd_expire)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
