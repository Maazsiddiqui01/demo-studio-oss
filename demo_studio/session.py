"""Saved sign-in sessions (Playwright storage_state): keep only what signing in needs.

After a render the recorder writes the refreshed session back (apps rotate refresh tokens).
Writing back the whole store once grew a file to about 120 MB (an app's column preferences in
localStorage) and the next render failed to open the browser. So the write-back keeps cookies
plus storage entries whose names look like auth, and refuses anything above MAX_BYTES.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

MAX_BYTES = 1_000_000
# Supabase (sb-<ref>-auth-token), MSAL, Auth0, Firebase, Okta and most hand-rolled token keys.
AUTH_KEY = re.compile(r"^sb-[a-z0-9]+-auth-token|token|session|auth|jwt|credential|oidc|msal|firebaseLocalStorage",
                      re.IGNORECASE)


def slim(state: dict) -> tuple[dict, list[str]]:
    """Return (cookies plus auth-looking storage entries, names of the entries dropped)."""
    dropped: list[str] = []
    origins = []
    for o in state.get("origins") or []:
        keep = {"origin": o.get("origin")}
        ls = []
        for item in o.get("localStorage") or []:
            if AUTH_KEY.search(item.get("name", "")):
                ls.append(item)
            else:
                dropped.append(f"{o.get('origin')} localStorage {item.get('name')}")
        keep["localStorage"] = ls
        if "indexedDB" in o:
            dbs = []
            for db in o.get("indexedDB") or []:
                if AUTH_KEY.search(db.get("name", "")):
                    dbs.append(db)
                else:
                    dropped.append(f"{o.get('origin')} indexedDB {db.get('name')}")
            if dbs:
                keep["indexedDB"] = dbs
        if ls or keep.get("indexedDB"):
            origins.append(keep)
    return {"cookies": list(state.get("cookies") or []), "origins": origins}, dropped


def write_back(state: dict, dest: Path, log=print) -> bool:
    """Write the slimmed session over dest. Refuses (and keeps the old file) above MAX_BYTES."""
    small, dropped = slim(state)
    data = json.dumps(small)
    if len(data.encode("utf-8")) > MAX_BYTES:
        log(f"  warning: the refreshed session is {len(data) / 1e6:.1f} MB even after keeping only auth entries; "
            f"not saved (the old session file is kept)")
        return False
    if dropped:
        log(f"  session write-back: kept cookies and {sum(len(o['localStorage']) for o in small['origins'])} auth "
            f"entries, dropped {len(dropped)} other storage entries")
    # Written in place, so the owner-only permissions set by `studio login` stay on the file.
    with open(dest, "w", encoding="utf-8") as f:
        f.write(data)
    return True
