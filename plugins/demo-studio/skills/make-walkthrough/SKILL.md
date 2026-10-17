---
name: make-walkthrough
description: "Make a narrated walkthrough video of a web app or a Windows desktop app (Power BI Desktop, Excel, any window) with the open-source demo-studio CLI, from a plain-English request: look at the app, write the script yourself, record the real browser with Playwright or the app window with UI Automation, add a local Kokoro voice, captions, zoom, subtitles and a framed look, check every frame, and hand over the MP4. Use when someone asks for a walkthrough, demo video, product video, LinkedIn or social clip, client handover video, onboarding or release-notes video, or a short proposal clip of an app, or asks to set up demo-studio."
---

# Make a walkthrough video with demo-studio

The person describes the video in plain words. You do everything else: install the tool if
needed, look at the app, write the storyboard, render, review every frame and hand over the file.
Never ask them to write YAML or run the commands. Ask only for what you cannot find out, in one
short message. Docs and source: https://github.com/Maazsiddiqui01/demo-studio-oss (`AGENTS.md`
there is the same guide for other agents; `docs/storyboard-format.md` has every key).

## 1. Setup (skip if `studio --version` works)

1. `uv --version`; if missing, install uv (Windows PowerShell:
   `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`;
   macOS and Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`).
2. `uv tool install git+https://github.com/Maazsiddiqui01/demo-studio-oss`
3. `studio doctor --download` (Chromium headless shell and the Kokoro model, about 350 MB, once).
4. For desktop apps (Windows only), install the `desktop` extra instead:
   `uv tool install --force "demo-studio[desktop] @ git+https://github.com/Maazsiddiqui01/demo-studio-oss"`.

No API key, account or paid service is involved.

## 2. Find out what to make

You need: the app (URL, or the repo and how to start it), what to show in order, who will watch
(anyone: `public`; one client about their own system: `handover`), whether a sign-in is needed,
and the format (16:9 by default; a square variant and subtitles for social feeds; 60 to 90 seconds
is typical). Read the repo and the running app before asking anything.

If the app shows real customer data and the video is public, stop: ask for demo or seeded data, or
build a small replica with made-up data.

## 3. Rules

1. **Never type a password and never ask for one.** For an app behind a sign-in, ask the person
   to run `studio login <name>`; a visible browser opens and they sign in themselves. Never read,
   print, commit or upload the saved session. `studio logout <name>` deletes it afterwards.
2. **Secrets are masked automatically** (password fields, key and token shapes, card numbers,
   webhook URLs). Add the app's settings pages and key fields under `redact:`. Masking does not
   reach inside iframes.
3. **Live systems are read-only.** A step that creates, edits, sends or deletes needs
   `live_write: true` and `confirmed_by_owner: true`, and the owner's yes comes from the person.
4. **Never fabricate.** Every claim in narration, captions and slides traces to a source listed
   under `sources:` (the README, the docs, the app itself).
5. **Public mode:** put client and company names, email domains and people's names in
   `banned_terms`; contact details fail unless the host is in `allowed_hosts`.
6. **Humanize the script before every render.** Run `/humanizer` on the narration, captions,
   title and closing text (install: `claude plugin marketplace add blader/humanizer`, then
   `claude plugin install humanizer@humanizer`; without it, read
   https://raw.githubusercontent.com/blader/humanizer/main/SKILL.md and apply it). Keep every fact,
   add none. One or two short sentences per step; the validator rejects em and en dashes.

## 4. Write the storyboard

Look at the pages first and pick stable selectors: `data-*` attributes, then Playwright role and
text selectors (`role=button[name="Save"]`, `text=Save`). Write `walkthroughs/<name>.yaml`:

```yaml
version: 1
name: my-app-tour                # output folder: out/my-app-tour/
mode: public
title: "Plan a day in *My App*"  # intro slide; *words* go on the highlight block
eyebrow: "MY APP"
intro_note: "Made-up demo data. Waiting time is sped up."
intro: { narration: "...", layout: auto }        # statement | product | agenda | cinematic | auto
outro: { heading: "...", bullets: ["..."], narration: "...", layout: auto, cta: "example.com/app" }
base_url: "http://localhost:5173"
serve: demo-app                  # optional: serve a local folder at base_url while recording
navigation: spa                  # spa (client-side routes) or load (full page loads)
voice: auto                      # female | male | auto (varies by video) | an id such as af_heart, am_michael
viewport: auto                   # fills the framed canvas at 1:1 (sharp text, thin margin)
sources: ["README.md#features"]
banned_terms: []
allowed_hosts: []
style:                           # public default: framed on a drifting wallpaper, 1920x1080
  background: auto               # a preset, a category (dark|blue|purple|orange|green|light), a list, or auto
  theme: petrol                  # slides and captions: petrol (dark) | kinetic (light) | navy
  captions: card                 # card | pill | lower
  subtitles: true                # burned-in narration, for feeds that autoplay muted
  music: ambient                 # optional quiet pad, ducked under the voice
variants:
  square: { viewport: [960, 854], style: { canvas: [1080, 1080], padding: 0.05 } }
delivery: { public: true, private_link: false, expires: null, local_only: false }
steps:
  - id: list
    route: "/"
    action: wait_for             # click | type | wait_for | scroll | goto | pause | hover
    target: "[data-demo=list]"
    caption: { n: 1, title: "Today's list", sub: "One task is due today" }
    narration: "Here is today's list."
  - id: add
    action: type
    target: "[data-demo=new-task]"
    text: "Book the team retro"
    zoom: auto                   # zoom in before the cursor moves (1.5), or a number 1.1 to 3
    caption: { n: 2, title: "Add a task", sub: "One line" }
    narration: "To add a task, type it in one line."
  - id: plan
    action: click
    target: "[data-demo=plan]"
    wait_for: "[data-demo=result]"
    speed_up: true               # the wait plays 4x faster and the caption says so
    caption: { n: 3, title: "Plan my day", sub: "The list is sorted" }
    narration: "Plan my day sorts the list. The wait is sped up."
```

About 150 to 200 words of narration make 60 to 90 seconds. Voices: `female` picks from af_heart,
af_bella and bf_emma, `male` from am_michael, am_fenrir, bm_george and am_puck; a step can set its
own `voice` for a second narrator. Keep the screen big: the window should fill the frame with only a thin wallpaper margin
(`padding` 0.04 or less; never shrink the recording to make room for wallpaper). Pick the look on purpose: a background
that suits the app's colours (`studio backgrounds` shows all 21) or `auto`, `theme: kinetic` for
light apps and brands, the `product` intro when the first screen is the best picture.
`studio slides walkthroughs/my-app.yaml` renders every intro, outro and caption design over the app.

## Desktop apps (Windows)

For an app window instead of a web page (`docs/desktop.md` has the details):

```yaml
driver: desktop
app: { window: "Sales.*Returns", maximize: true }   # a regex for the window title; launch: "app.exe" to start it
steps:
  - id: returns
    action: click
    target: "name=Returns; type=TabItem"   # or at=640,360 in window pixels where controls have no names
    caption: { n: 1, title: "Returns", sub: "By product and store" }
    narration: "The returns page breaks returns down by product and store."
  - id: next
    action: key
    keys: "^{PGDN}"                        # pywinauto syntax: ^ Ctrl, % Alt, + Shift, {ENTER}
    caption: { n: 2, title: "Next page", sub: "Ctrl and Page Down" }
    narration: "Control and page down moves to the next page."
```

- `studio windows` lists windows; `studio inspect "<title>"` prints controls with selectors. Report
  canvases (Power BI), charts and custom-drawn apps have no names: screenshot the window and use
  `at=X,Y`.
- The recording moves the real mouse and keyboard. Tell the person first and ask them not to touch
  the machine; suggest Do Not Disturb. Notifications and other windows over the app are blurred
  automatically. Never change their system settings.
- Reset the app before each render (filters and sliders keep their state) and never save their
  file. A `key` step that saves, deletes or submits counts as a write on a live system.
- `studio render <file> --reassemble` encodes again from the kept recording without recording.
- Maximize the window or give it a wide `app.size`: the recording is scaled up to fill the frame,
  and a tall, narrow window leaves wide margins.

## 5. Render, review, hand over

```bash
studio validate walkthroughs/my-app.yaml
studio render walkthroughs/my-app.yaml
studio render walkthroughs/my-app.yaml --variant square
```

**Review every frame yourself.** Open each image in `out/<name>/qa/sheets/` (handover:
`out/clients/<client>/<name>/qa/sheets/`): captions and subtitles readable, rings and zoom on the
right elements, slides correct, no real names or contact details (public), no visible secret
(handover). Fix the storyboard and render again until it is right, then record the verdict:

```bash
studio check out/my-app-tour --frames pass --note "what you checked"
```

Give the person the MP4 path, the length and the gate result from `REPORT.md`. Offer
`studio publish out/<name>` (a folder or their own server, `docs/publishing.md`) if they want a
web page. Handover videos stay local unless they ask for a private link.
