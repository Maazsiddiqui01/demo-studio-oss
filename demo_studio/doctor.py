"""`studio doctor`: what is installed, what will be downloaded on first use, what is missing."""
from __future__ import annotations

import platform
import shutil
import sys

from . import __version__, config


def _ok(log, good: bool | None, name: str, detail: str) -> None:
    mark = {True: "ok  ", False: "FAIL", None: "note"}[good]
    log(f"  [{mark}] {name:13s} {detail}")


def doctor(log=print, download: bool = False) -> int:
    fails = 0
    log(f"demo-studio {__version__} on Python {platform.python_version()}, {platform.system()} {platform.machine()}")

    # ffmpeg
    try:
        from .tools import ffmpeg_exe, ffmpeg_version
        _ok(log, True, "ffmpeg", f"{ffmpeg_version()} ({ffmpeg_exe()})")
    except Exception as e:
        fails += 1
        _ok(log, False, "ffmpeg", str(e))

    # browser
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            try:
                b = pw.chromium.launch()
                _ok(log, True, "browser", f"Chromium {b.version}")
                b.close()
            except Exception as e:
                if "Executable doesn't exist" not in str(e):
                    raise
                if download:
                    from .tools import install_chromium
                    install_chromium(log=log)
                    _ok(log, True, "browser", "Chromium headless shell installed")
                else:
                    _ok(log, None, "browser", "not installed yet: downloaded on the first render (or run `studio doctor --download`)")
    except Exception as e:
        fails += 1
        _ok(log, False, "browser", f"Playwright could not start Chromium: {e}")

    # voice
    from . import tts
    b = tts.backend()
    if b == "kokoro":
        try:
            _ok(log, True, "voice", f"Kokoro-82M on {tts.device()} (torch)")
        except Exception as e:
            fails += 1
            _ok(log, False, "voice", f"kokoro is installed but torch failed: {e}")
    else:
        try:
            import kokoro_onnx  # noqa: F401
            d = tts.onnx_dir()
            have = all((d / n).exists() for n in tts.ONNX_FILES)
            if not have and download:
                tts.ensure_onnx_models(log=log)
                have = True
            _ok(log, True if have else None, "voice",
                f"Kokoro-82M on the CPU (kokoro-onnx); model files {'in ' + str(d) if have else 'downloaded on the first render (about 350 MB)'}")
        except ImportError:
            fails += 1
            _ok(log, False, "voice", "neither kokoro nor kokoro-onnx is installed: pip install kokoro-onnx")

    # GPU (optional)
    try:
        import torch
        if torch.cuda.is_available():
            _ok(log, True, "gpu", torch.cuda.get_device_name(0))
        else:
            _ok(log, None, "gpu", "no CUDA GPU; the CPU voice is used")
    except ImportError:
        _ok(log, None, "gpu", "torch not installed; the CPU voice is used (install the [gpu] extra for Kokoro on CUDA)")

    # speech check (optional)
    try:
        import faster_whisper  # noqa: F401
        _ok(log, True, "speech check", "faster-whisper installed: the gate compares the audio with the script")
    except ImportError:
        _ok(log, None, "speech check", "faster-whisper not installed; the gate skips it (install the [check] extra)")

    # workspace
    cache = config.cache_dir()
    free = shutil.disk_usage(cache if cache.exists() else cache.anchor or "/").free / 1e9
    _ok(log, True, "workspace", f"{config.home()} (renders in {config.out_root()})")
    _ok(log, True if free > 2 else None, "cache", f"{cache} ({free:.0f} GB free)")
    pub = config.settings().get("publish") or {}
    _ok(log, None, "publish", f"target {pub.get('target', 'folder')}" + (f", {pub['base_url']}" if pub.get("base_url") else "")
        + ("" if pub else " (no demo-studio.yaml: `studio publish` writes to ./site)"))
    log("Ready." if not fails else f"{fails} problem(s) above.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(doctor())
