"""Publish a render: to a local folder (any static host can serve it) or to your own server
over ssh. Settings live in demo-studio.yaml (workspace) or the user config file:

    publish:
      target: folder            # folder | ssh
      folder: site              # folder target: where the site is written (relative to the file)
      base_url: https://videos.example.com   # the public address of that site (optional for folder)
      # ssh target:
      ssh: [ssh, me@my-server]  # command prefix; "{bash}" becomes Git Bash on Windows
      remote_dir: /srv/demo-studio
      private_links: caddy      # handover private links: Caddy basic auth (see docs/publishing.md)
      caddy_container: demo-studio-web
      host_check: false         # gate item 6 needs out/vps_check.json when true

Layout, the same in a folder and on a server:
    <root>/www/media/<slug>/{video.mp4,captions.vtt,poster.jpg}
    <root>/www/v/<slug>/index.html       the embed page
    <root>/www/index.html, videos.json   the list of public videos
    <root>/private/<random>/             handover private links (ssh + caddy only)
Handover videos are never published publicly; by default they stay local.
"""
from __future__ import annotations

import datetime as dt
import html
import io
import json
import os
import secrets
import shutil
import ssl
import subprocess
import tarfile
import urllib.error
import urllib.request
from base64 import b64encode
from pathlib import Path

from .config import TEMPLATES, settings

FILES = ("video.mp4", "captions.vtt", "poster.jpg")


class PublishError(Exception):
    pass


def _bash() -> str:
    """Git Bash on Windows (a bare "bash" there resolves to the WSL stub), plain bash elsewhere."""
    if os.name == "nt":
        for p in (r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files\Git\usr\bin\bash.exe"):
            if Path(p).exists():
                return p
    return shutil.which("bash") or "bash"


def conf() -> dict:
    return dict(settings().get("publish") or {})


def _base(c: dict) -> str:
    return str(c.get("base_url") or "").rstrip("/")


# ---- targets -----------------------------------------------------------------------------
class FolderTarget:
    kind = "folder"

    def __init__(self, c: dict):
        root = Path(c.get("folder") or "site")
        self.root = root if root.is_absolute() else Path(c.get("_dir") or ".") / root

    def put(self, files: dict[str, bytes], dest: str) -> None:
        d = self.root / dest
        tmp = d.with_name(d.name + ".incoming")
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        for name, data in files.items():
            (tmp / name).write_bytes(data)
        shutil.rmtree(d, ignore_errors=True)
        tmp.replace(d)

    def read(self, path: str) -> bytes | None:
        p = self.root / path
        return p.read_bytes() if p.exists() else None

    def write(self, path: str, data: bytes) -> None:
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)


class SshTarget:
    kind = "ssh"

    def __init__(self, c: dict):
        cmd = c.get("ssh")
        if not cmd or not c.get("remote_dir"):
            raise PublishError("publish.target ssh needs publish.ssh (a command list) and publish.remote_dir")
        base = Path(c.get("_dir") or ".")
        self.cmd = []
        for part in ([cmd] if isinstance(cmd, str) else cmd):
            part = str(part).replace("{bash}", _bash())
            if part.endswith((".sh", ".ps1", ".cmd")) and not Path(part).is_absolute() and (base / part).exists():
                part = str(base / part)
            self.cmd.append(part)
        self.root = str(c["remote_dir"]).rstrip("/")

    def run(self, command: str, stdin: bytes | None = None, check: bool = True) -> subprocess.CompletedProcess:
        r = subprocess.run(self.cmd + [command], input=stdin, capture_output=True)
        if check and r.returncode != 0:
            raise PublishError(f"ssh failed ({r.returncode}): {command[:120]}\n{r.stderr.decode(errors='replace')[-800:]}")
        return r

    def put(self, files: dict[str, bytes], dest: str) -> None:
        """Stream a tar of {name: bytes} into dest, replacing it atomically."""
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            for name, data in files.items():
                ti = tarfile.TarInfo(name)
                ti.size, ti.mode, ti.mtime = len(data), 0o644, int(dt.datetime.now().timestamp())
                tar.addfile(ti, io.BytesIO(data))
        d = f"{self.root}/{dest}"
        tmp = f"{d}.incoming"
        self.run(f"set -e; rm -rf '{tmp}'; mkdir -p '{tmp}'; tar -xf - -C '{tmp}'; chmod 755 '{tmp}'; "
                 f"rm -rf '{d}.old'; if [ -d '{d}' ]; then mv '{d}' '{d}.old'; fi; mv '{tmp}' '{d}'; rm -rf '{d}.old'",
                 stdin=buf.getvalue())

    def read(self, path: str) -> bytes | None:
        r = self.run(f"cat '{self.root}/{path}' 2>/dev/null || true")
        return r.stdout or None

    def write(self, path: str, data: bytes) -> None:
        p = f"{self.root}/{path}"
        self.run(f"mkdir -p \"$(dirname '{p}')\" && cat > '{p}.tmp' && mv '{p}.tmp' '{p}'", stdin=data)


def target(c: dict | None = None):
    c = conf() if c is None else c
    kind = c.get("target", "folder")
    if kind == "folder":
        return FolderTarget(c)
    if kind == "ssh":
        return SshTarget(c)
    raise PublishError(f"publish.target: folder or ssh, not {kind!r}")


# ---- pages -------------------------------------------------------------------------------
def embed_page(sb, slug: str, prefix: str, base: str, size: tuple[int, int]) -> bytes:
    t = (TEMPLATES / "embed.html").read_text(encoding="utf-8")
    vals = {"title": sb.plain_title, "description": sb.intro_note or sb.plain_title, "base": base, "slug": slug,
            "width": str(size[0]), "height": str(size[1])}
    for k, v in vals.items():
        t = t.replace("{{" + k + "}}", html.escape(v, quote=True))
    if not base:  # no public address known: drop the share-card tags that need absolute URLs
        t = "\n".join(line for line in t.splitlines() if 'property="og:' not in line)
    if prefix != "media":  # private pages: own folder, no share-card tags, noindex
        t = "\n".join(line for line in t.splitlines() if 'property="og:' not in line)
        t = t.replace(f"/media/{slug}/", "")
        t = t.replace("<head>", '<head>\n<meta name="robots" content="noindex, nofollow">', 1)
    return t.encode("utf-8")


def _site_index(entries: list[dict]) -> bytes:
    items = "\n".join(
        f'<li><a href="/v/{html.escape(e["slug"])}/">{html.escape(e["title"])}</a> '
        f'<small>{html.escape(e["published"])}</small></li>' for e in entries)
    return (f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Walkthrough videos</title><style>body{{font-family:system-ui,sans-serif;max-width:760px;margin:60px auto;padding:0 20px;color:#0f172a}}
li{{margin:10px 0}}small{{color:#64748b;margin-left:8px}}</style></head><body><h1>Walkthrough videos</h1><ul>
{items}
</ul></body></html>""").encode("utf-8")


def http(url: str, method: str = "GET", auth: tuple[str, str] | None = None, rng: str | None = None) -> dict:
    req = urllib.request.Request(url, method=method)
    if auth:
        req.add_header("Authorization", "Basic " + b64encode(f"{auth[0]}:{auth[1]}".encode()).decode())
    if rng:
        req.add_header("Range", rng)
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl.create_default_context()) as r:
            r.read(1024)
            return {"status": r.status, "type": r.headers.get("Content-Type"), "robots": r.headers.get("X-Robots-Tag"),
                    "length": r.headers.get("Content-Length")}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "type": e.headers.get("Content-Type"), "robots": e.headers.get("X-Robots-Tag")}
    except urllib.error.URLError as e:
        return {"status": None, "error": str(e.reason)}


def _video_size(out: Path, sb) -> tuple[int, int]:
    try:
        return tuple(json.loads((out / "timeline_out.json").read_text(encoding="utf-8"))["size"])
    except Exception:
        return sb.viewport


# ---- publish -----------------------------------------------------------------------------
def publish_public(sb, out: Path, log=print) -> dict:
    c = conf()
    t = target(c)
    base = _base(c)
    slug = sb.name
    files = {f: (out / f).read_bytes() for f in FILES}
    where = f"{t.root}/www/media/{slug}/" if t.kind == "folder" else (f"{base}/media/{slug}/" if base else f"{t.root}/www/media/{slug}/")
    log(f"publishing {sum(len(v) for v in files.values()) / 1e6:.1f} MB to {where}")
    t.put(files, f"www/media/{slug}")
    t.put({"index.html": embed_page(sb, slug, "media", base, _video_size(out, sb))}, f"www/v/{slug}")
    raw = t.read("www/videos.json")
    entries = [e for e in json.loads((raw or b"[]").decode() or "[]") if e["slug"] != slug]
    entries.append({"slug": slug, "title": sb.plain_title, "published": dt.date.today().isoformat()})
    entries.sort(key=lambda e: e["slug"])
    t.write("www/videos.json", json.dumps(entries, indent=1).encode())
    t.write("www/index.html", _site_index(entries))
    res = {"kind": "public", "target": t.kind, "published_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    if t.kind == "folder":
        res["path"] = str(t.root / "www" / "v" / slug)
    if base:
        urls = {"page": f"{base}/v/{slug}/", "video": f"{base}/media/{slug}/video.mp4",
                "captions": f"{base}/media/{slug}/captions.vtt", "poster": f"{base}/media/{slug}/poster.jpg"}
        res["urls"] = urls
        if t.kind == "ssh" or c.get("check_urls"):
            checks = {k: http(u) for k, u in urls.items()}
            checks["video_range"] = http(urls["video"], rng="bytes=0-1023")
            res["checks"] = checks
            res["ok"] = (all(ch["status"] == 200 for k, ch in checks.items() if k != "video_range")
                         and checks["video_range"]["status"] == 206 and (checks["video"]["type"] or "").startswith("video/mp4"))
            return res
    res["ok"] = all((Path(t.root) / "www" / "media" / slug / f).exists() for f in FILES) if t.kind == "folder" else True
    return res


def publish_private(sb, out: Path, log=print, slug: str | None = None, expires: str | None = None) -> dict:
    """A basic-auth link with an expiry date. Needs the ssh target with private_links: caddy."""
    c = conf()
    t = target(c)
    if t.kind != "ssh" or c.get("private_links") != "caddy":
        raise PublishError("private links need publish.target: ssh with private_links: caddy (docs/publishing.md); "
                           "otherwise keep the handover video local (delivery.local_only: true)")
    import bcrypt
    base = _base(c)
    container = c.get("caddy_container", "demo-studio-web")
    slug = slug or secrets.token_hex(12)
    password = secrets.token_urlsafe(18)
    expires = expires or str(sb.delivery.get("expires"))
    dt.date.fromisoformat(expires)
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()
    files = {f: (out / f).read_bytes() for f in FILES}
    files["index.html"] = embed_page(sb, slug, "private", base, _video_size(out, sb))
    files["meta.json"] = json.dumps({"expires": expires, "created": dt.date.today().isoformat()}).encode()
    log(f"uploading a private link that expires {expires}")
    t.put(files, f"private/{slug}")
    route = (f"# private link, expires {expires}\nhandle_path /private/{slug}/* {{\n\tbasic_auth {{\n\t\tviewer {pw_hash}\n\t}}\n"
             f"\theader X-Robots-Tag \"noindex, nofollow\"\n\troot * /srv/private/{slug}\n\tfile_server\n}}\n")
    t.run(f"cat > {t.root}/web/private.d/{slug}.caddy", stdin=route.encode())
    v = t.run(f"docker exec {container} caddy validate --config /etc/caddy/Caddyfile", check=False)
    if v.returncode != 0:
        t.run(f"rm -f {t.root}/web/private.d/{slug}.caddy")
        raise PublishError("Caddy rejected the private route; it was removed:\n" + v.stderr.decode(errors="replace")[-600:])
    t.run(f"docker exec {container} caddy reload --config /etc/caddy/Caddyfile")
    url = f"{base}/private/{slug}/"
    checks = {
        "no_password": http(url),
        "wrong_password": http(url, auth=("viewer", "wrong")),
        "page": http(url, auth=("viewer", password)),
        "video": http(url + "video.mp4", auth=("viewer", password)),
        "video_range": http(url + "video.mp4", auth=("viewer", password), rng="bytes=0-1023"),
    }
    ok = (checks["no_password"]["status"] == 401 and checks["wrong_password"]["status"] == 401
          and checks["page"]["status"] == 200 and checks["video"]["status"] == 200
          and checks["video_range"]["status"] == 206
          and all("noindex" in (ch.get("robots") or "") for ch in checks.values()))
    secret_file = out / "PRIVATE_LINK.txt"
    secret_file.write_text(f"URL: {url}\nUser: viewer\nPassword: {password}\nExpires: {expires} (deleted by demo-studio-expire)\n",
                           encoding="utf-8")
    return {"ok": ok, "kind": "private", "target": "ssh", "url": url, "user": "viewer", "expires": expires, "slug": slug,
            "password_file": str(secret_file), "checks": checks,
            "published_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}


def publish(sb, out: Path, log=print) -> dict:
    d = sb.delivery
    if sb.mode == "handover":
        if not d.get("private_link"):
            res = {"ok": True, "kind": "local", "note": "local only by design: you deliver the MP4 yourself",
                   "path": str(out / "video.mp4")}
        else:
            res = publish_private(sb, out, log=log)
    elif d.get("public"):
        res = publish_public(sb, out, log=log)
    else:
        res = {"ok": True, "kind": "local", "note": "delivery.public is false: nothing uploaded"}
    (out / "delivery.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    return res
