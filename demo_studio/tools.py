"""External tools: ffmpeg (from PATH, or the copy bundled with imageio-ffmpeg) and Chromium
(installed by Playwright on first use)."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=None)
def ffmpeg_exe() -> str:
    """DEMO_STUDIO_FFMPEG, then ffmpeg on PATH, then imageio-ffmpeg's bundled binary."""
    env = os.environ.get("DEMO_STUDIO_FFMPEG")
    if env:
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:  # pragma: no cover - depends on the machine
        raise RuntimeError("ffmpeg not found: install it, or `pip install imageio-ffmpeg`") from e


def ffmpeg(*args: str, cwd: Path | None = None) -> None:
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", *args]
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd)}\n{r.stderr[-2000:]}")


def ffmpeg_stderr(*args: str) -> str:
    """Run ffmpeg for its analysis output (volumedetect, silencedetect, -i)."""
    r = subprocess.run([ffmpeg_exe(), "-hide_banner", *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.stderr


def probe(path: Path) -> dict:
    """What the gate needs from a media file, read from `ffmpeg -i` (no ffprobe required):
    {"duration": s, "video": {"codec", "width", "height"}, "audio": {"codec"}}."""
    err = ffmpeg_stderr("-i", str(path))
    out: dict = {"duration": None, "video": {}, "audio": {}}
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
    if m:
        out["duration"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    m = re.search(r"Stream #\S+.*?: Video: (\w+).*?, (\d{2,5})x(\d{2,5})", err)
    if m:
        out["video"] = {"codec": m.group(1), "width": int(m.group(2)), "height": int(m.group(3))}
    m = re.search(r"Stream #\S+.*?: Audio: (\w+)", err)
    if m:
        out["audio"] = {"codec": m.group(1)}
    return out


def ffmpeg_version() -> str:
    r = subprocess.run([ffmpeg_exe(), "-version"], capture_output=True, text=True)
    return (r.stdout.splitlines() or ["?"])[0]


def install_chromium(headed: bool = False, log=print) -> None:
    """Playwright's browsers: the small headless shell for renders, full Chromium for `login`."""
    args = [sys.executable, "-m", "playwright", "install", "chromium"]
    if not headed:
        args.append("--only-shell")
    log(f"First run: downloading {'Chromium' if headed else 'the Chromium headless shell'} for Playwright "
        "(one time, about 100 to 170 MB)")
    subprocess.run(args, check=True)


async def launch_chromium(pw, headless: bool = True, log=print, **kw):
    """pw.chromium.launch(), installing the browser first if it is missing."""
    try:
        return await pw.chromium.launch(headless=headless, **kw)
    except Exception as e:
        if "Executable doesn't exist" not in str(e) and "playwright install" not in str(e):
            raise
    install_chromium(headed=not headless, log=log)
    return await pw.chromium.launch(headless=headless, **kw)
