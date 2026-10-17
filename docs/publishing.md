# Publishing

`studio publish <out-dir>` sends a finished render to a folder on your machine or to your own
server. What it does depends on the mode:

- **Public video with `delivery.public: true`:** uploads the video, captions, poster and a small
  embed page, and updates the site's video list.
- **Handover video with `delivery.private_link: true`:** uploads a private, expiring link. Needs
  the ssh target and Caddy.
- **Anything else:** uploads nothing and records "local only".

The result is printed as JSON and saved as `delivery.json`. The command exits 1 if a check fails.

## Settings files

Settings live under a `publish:` section in a YAML file. Two files are read:

1. The user file: `%APPDATA%\demo-studio\config.yaml` on Windows, and
   `$XDG_CONFIG_HOME/demo-studio/config.yaml` (default `~/.config/demo-studio/config.yaml`) on
   macOS and Linux.
2. The workspace file `demo-studio.yaml`. The workspace is the folder in `DEMO_STUDIO_HOME`, or the
   current folder.

The workspace file wins, key by key. Relative paths in the settings (`folder`, and script names in
`ssh`) are relative to the folder of the workspace file, or of the user file when the workspace has
no `publish:` section. `studio doctor` shows the target in use.
With no settings at all, `studio publish` writes to `./site`.

```yaml
publish:
  target: folder                       # folder | ssh
  folder: site                         # folder target: where the site is written
  base_url: https://videos.example.com # public address of the site
  # ssh target:
  ssh: [ssh, my-server]                # command prefix (a host name or a Host alias from your ssh config)
  remote_dir: /srv/demo-studio         # site root on the server
  private_links: caddy                 # turns on handover private links
  caddy_container: demo-studio-web     # Docker container running Caddy
  host_check: false                    # gate item 6 needs out/vps_check.json when true
```

| Key | Default | Meaning |
|---|---|---|
| `target` | `folder` | `folder` writes to a local folder. `ssh` writes to a server over ssh. |
| `folder` | `site` | Folder target: where the site is written. |
| `base_url` | none | Public address of the site, without a trailing slash. Needed to print and check URLs, to build private link URLs, and for share-card tags in the embed page. |
| `check_urls` | `false` | Folder target: also fetch the URLs after publishing (needs `base_url`). The ssh target always checks them when `base_url` is set. |
| `ssh` | none | Ssh target: the command prefix as a list. The tool appends the remote command as the last argument, so `[ssh, my-server]` runs `ssh my-server '<command>'`. The text `{bash}` becomes Git Bash on Windows. A script name ending in `.sh`, `.ps1` or `.cmd` is looked up next to the settings file. |
| `remote_dir` | none | Ssh target: the site root on the server. Required with `ssh`. |
| `private_links` | none | `caddy` enables private links. Anything else disables them. |
| `caddy_container` | `demo-studio-web` | Name of the Docker container that runs Caddy. |
| `host_check` | `false` | When true, gate item 6 needs `vps_check.json` ([quality-gate.md](quality-gate.md)). |

Ssh needs key-based login, because the tool cannot answer a password prompt. The server needs `sh`
and standard tools such as `tar`, `cat`, `mv` and `rm`; private links also need `docker`. Private
links need bcrypt on your machine: install the `server` extra (see the README).

## Output layout

The same layout is used in a folder and on a server, under the root (`folder`, or `remote_dir`).
The last two lines exist only on an ssh server:

```
<root>/www/media/<slug>/video.mp4        the video, captions.vtt and poster.jpg beside it
<root>/www/v/<slug>/index.html           the embed page (a player, with share-card tags)
<root>/www/index.html                    a list of public videos
<root>/www/videos.json                   the same list as data
<root>/private/<random>/                 a private link: the three files, index.html, meta.json
<root>/web/private.d/<random>.caddy      the route for that private link
```

`<slug>` is the storyboard `name`. The links to share are `<base_url>/v/<slug>/` for the page and
`<base_url>/media/<slug>/video.mp4` for the file. The page title and the list entry use the
storyboard `title` without its asterisks. Each upload goes to a temporary folder first and then
replaces the old one.

Serve `www/` at the root of a host name. The embed page and the list use absolute paths such as
`/media/<slug>/video.mp4`, so a sub-path breaks them. For the folder target any static host
works: point it at `<folder>/www`.

## Serving the site with Caddy

This example serves `www/` on `videos.example.com` and imports private link routes. Create
`/srv/demo-studio/web/Caddyfile`:

```
videos.example.com {
	root * /srv/www

	# One file per private link, written by `studio publish`.
	import /etc/caddy/private.d/*.caddy

	file_server
}
```

Run Caddy in a container named `demo-studio-web` (the default `caddy_container`) with
`/srv/demo-studio/docker-compose.yml`:

```yaml
services:
  web:
    image: caddy:2
    container_name: demo-studio-web
    restart: unless-stopped
    ports: ["80:80", "443:443"]
    volumes:
      - ./web/Caddyfile:/etc/caddy/Caddyfile:ro
      - ./web/private.d:/etc/caddy/private.d:ro
      - ./www:/srv/www:ro
      - ./private:/srv/private:ro
      - caddy_data:/data
      - caddy_config:/config
volumes:
  caddy_data:
  caddy_config:
```

Prepare the folders and start it. Point the DNS record of `videos.example.com` at the server first,
so Caddy can get a certificate by itself.

```
mkdir -p /srv/demo-studio/www /srv/demo-studio/private /srv/demo-studio/web/private.d
cd /srv/demo-studio && docker compose up -d
```

`private.d` must exist before the first private link, but it can be empty: Caddy does not treat an
import glob with no matches as an error. Use a current Caddy 2 image: the generated
routes use `basic_auth`, which is the name from Caddy 2.8 on. The ssh user needs to run `docker`.

## Private links

A private link is for a handover video. Set `delivery: { private_link: true, expires: 2026-12-31 }`
and run `studio publish`. The tool then:

1. makes a random 24 character folder name and a random password,
2. uploads the video, captions, poster, a no-index embed page and `meta.json` with the expiry date
   to `<root>/private/<random>/`,
3. writes a Caddy route for `/private/<random>/*` with basic auth (user `viewer`, a bcrypt hash of
   the password) and an `X-Robots-Tag: noindex, nofollow` header,
4. runs `caddy validate`, removes the route again if Caddy rejects it, otherwise runs
   `caddy reload`,
5. checks that no password and a wrong password both give 401, the right password gives 200 for the
   page and the video and 206 for a range request, and that every response says noindex.

The link, user name, password and expiry go to `PRIVATE_LINK.txt` in the output folder. The
password is not printed anywhere else. Treat the file as a secret and send it to the client over a
channel you trust. The link works through the end of the expiry date (UTC).

## Expiring links

`expire.py` deletes private links whose date has passed, removes their Caddy routes and reloads
Caddy. It uses only the Python standard library and reads two environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `DEMO_STUDIO_HOME` | `/srv/demo-studio` | The site root on the server (your `remote_dir`). |
| `DEMO_STUDIO_CADDY_CONTAINER` | `demo-studio-web` | The Caddy container to reload. |

A folder with no readable `meta.json` is kept. `--dry-run` only reports. It logs to stdout and to
`<root>/logs/expire.log`. Run it every day. On the server, either install the package and use
`studio expire`, or copy the one file (`demo_studio/expire.py` in the package) and run it with
the system Python. A systemd service and timer for the copied file:

```ini
# /etc/systemd/system/demo-studio-expire.service
[Unit]
Description=Delete expired demo-studio private links

[Service]
Type=oneshot
User=me
Environment=DEMO_STUDIO_HOME=/srv/demo-studio
Environment=DEMO_STUDIO_CADDY_CONTAINER=demo-studio-web
ExecStart=/usr/bin/python3 /srv/demo-studio/bin/expire.py
```

```ini
# /etc/systemd/system/demo-studio-expire.timer
[Unit]
Description=Run demo-studio-expire every day

[Timer]
OnCalendar=*-*-* 03:30:00
Persistent=true

[Install]
WantedBy=timers.target
```

```
sudo systemctl daemon-reload
sudo systemctl enable --now demo-studio-expire.timer
sudo systemctl start demo-studio-expire.service     # a first run, to test
```

The user in `User=` must be able to run `docker` and write to `DEMO_STUDIO_HOME`.
