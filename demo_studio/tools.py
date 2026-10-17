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


STALL_SECONDS = 180  # no encoding progress for this long means ffmpeg is stuck


def ffmpeg(*args: str, cwd: Path | None = None) -> None:
    """Run ffmpeg and raise on failure. ffmpeg 7 and 8 can deadlock at the end of a long filter
    graph when the machine is busy (every thread waiting, 0% CPU, forever), so the run is watched
    through -progress; a stalled run is killed and tried once more with single-threaded filtering."""
    base = [ffmpeg_exe(), "-hide_banner", "-nostdin", "-loglevel", "error", "-y"]
    for extra in ([], ["-filter_complex_threads", "1"]):
        cmd = base + extra + list(args)
        rc, err = _run_watched(cmd, cwd)
        if rc == 0:
            return
        if rc is not None:
            raise RuntimeError(f"ffmpeg failed: {' '.join(cmd)}\n{err[-2000:]}")
        if not extra:
            print(f"  ffmpeg made no progress for {STALL_SECONDS}s and was stopped; trying again "
                  "with single-threaded filtering", flush=True)
    raise RuntimeError(f"ffmpeg made no progress for {STALL_SECONDS}s, twice: {' '.join(cmd)}")


def _progress_mark(path: str) -> tuple:
    """The newest out_time_us, total_size and progress values in an ffmpeg -progress file."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ()
    found = {}
    for key in ("out_time_us", "total_size", "frame", "progress"):
        i = text.rfind(key + "=")
        if i >= 0:
            found[key] = text[i:text.find("\n", i)]
    return tuple(sorted(found.items()))


def _run_watched(cmd: list[str], cwd: Path | None) -> tuple[int | None, str]:
    """(returncode, stderr), or (None, stderr) when the run stalled and was killed. stdin is closed
    (ffmpeg started from a background shell otherwise waits on it) and stderr goes to a file, so a
    chatty run can never block on a full pipe."""
    import tempfile
    import time
    fd, prog = tempfile.mkstemp(prefix="demo-studio-ffmpeg-", suffix=".progress")
    os.close(fd)
    try:
        with tempfile.TemporaryFile() as err:
            full = cmd[:1] + ["-progress", "file:" + prog, "-stats_period", "1"] + cmd[1:]
            proc = subprocess.Popen(full, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=err)
            mark, t_mark = None, time.time()
            while True:
                try:
                    rc = proc.wait(timeout=2)
                    break
                except subprocess.TimeoutExpired:
                    pass
                m = _progress_mark(prog)
                if m != mark:
                    mark, t_mark = m, time.time()
                elif time.time() - t_mark > STALL_SECONDS:
                    proc.kill()
                    proc.wait()
                    rc = None
                    break
            err.seek(0)
            return rc, err.read().decode("utf-8", errors="replace")
    finally:
        try:
            os.unlink(prog)
        except OSError:
            pass


def ffmpeg_stderr(*args: str) -> str:
    """Run ffmpeg for its analysis output (volumedetect, silencedetect, -i)."""
    r = subprocess.run([ffmpeg_exe(), "-hide_banner", "-nostdin", *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
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
    r = subprocess.run([ffmpeg_exe(), "-version"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
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
