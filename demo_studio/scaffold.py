"""`studio init`: write a starter storyboard and a tiny demo app that renders as is."""
from __future__ import annotations

import shutil
from pathlib import Path

from .config import TEMPLATES

FILES = ["walkthrough.yaml", "demo-app/index.html"]


def init(folder: Path, force: bool = False, log=print) -> int:
    folder.mkdir(parents=True, exist_ok=True)
    src = TEMPLATES / "init"
    existing = [f for f in FILES if (folder / f).exists()]
    if existing and not force:
        log(f"Not overwriting {', '.join(existing)} in {folder.resolve()} (use --force).")
        return 1
    for f in FILES:
        (folder / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src / f, folder / f)
        log(f"  wrote {folder / f}")
    here = "" if folder.resolve() == Path.cwd().resolve() else f"cd {folder}\n  "
    log("")
    log("Next:")
    log(f"  {here}studio render walkthrough.yaml")
    log("The first render downloads the browser and the voice model once (about 450 MB in total).")
    log("The video lands in out/tidy-tasks-tour/video.mp4, with REPORT.md and contact sheets in qa/sheets/.")
    return 0
