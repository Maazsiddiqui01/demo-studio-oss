#!/usr/bin/env python3
"""demo-studio-expire: delete private links past their expiry date (runs daily on the server).

Standard library only, so the systemd unit can run it with /usr/bin/python3.
Layout: <home>/private/<slug>/meta.json  {"expires": "YYYY-MM-DD"}
        <home>/web/private.d/<slug>.caddy (the link's basic-auth route in demo-studio-web)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path(os.environ.get("DEMO_STUDIO_HOME", "/srv/demo-studio"))
CONTAINER = os.environ.get("DEMO_STUDIO_CADDY_CONTAINER", "demo-studio-web")


def log(msg: str) -> None:
    line = f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M:%S}Z {msg}"
    print(line, flush=True)
    try:
        (HOME / "logs").mkdir(parents=True, exist_ok=True)
        with open(HOME / "logs" / "expire.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def reload_web() -> bool:
    v = subprocess.run(["docker", "exec", CONTAINER, "caddy", "validate", "--config", "/etc/caddy/Caddyfile"],
                       capture_output=True, text=True)
    if v.returncode != 0:
        log(f"validate failed, not reloading: {v.stderr.strip()[-400:]}")
        return False
    r = subprocess.run(["docker", "exec", CONTAINER, "caddy", "reload", "--config", "/etc/caddy/Caddyfile"],
                       capture_output=True, text=True)
    log("reloaded demo-studio-web" if r.returncode == 0 else f"reload failed: {r.stderr.strip()[-400:]}")
    return r.returncode == 0


def expire(dry_run: bool = False, today: dt.date | None = None) -> int:
    today = today or dt.datetime.now(dt.timezone.utc).date()
    priv, snippets = HOME / "private", HOME / "web" / "private.d"
    changed = False
    for d in sorted(p for p in priv.glob("*") if p.is_dir()) if priv.exists() else []:
        try:
            meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
            expires = dt.date.fromisoformat(meta["expires"])
        except Exception as e:  # no readable expiry: keep it, but say so
            log(f"{d.name}: no valid meta.json ({e}); kept")
            continue
        if today > expires:
            log(f"{d.name}: expired {expires}; {'would delete' if dry_run else 'deleting'}")
            if not dry_run:
                shutil.rmtree(d)
                (snippets / f"{d.name}.caddy").unlink(missing_ok=True)
                changed = True
    # a route whose folder is gone serves nothing; remove it
    for s in snippets.glob("*.caddy") if snippets.exists() else []:
        if s.stem.startswith("_"):
            continue
        if not (priv / s.stem).exists():
            log(f"{s.stem}: route without a folder; {'would remove' if dry_run else 'removing'}")
            if not dry_run:
                s.unlink()
                changed = True
    if changed:
        reload_web()
    else:
        log("nothing expired")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    return expire(dry_run="--dry-run" in argv)


if __name__ == "__main__":
    sys.exit(main())
