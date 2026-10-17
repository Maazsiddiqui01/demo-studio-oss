# demo-studio: guide for coding agents

This file is for an AI coding agent (Claude Code, Codex, Cursor, Copilot, Windsurf and others) that
a person has asked to set up demo-studio, or to make a walkthrough video of an app.

The person should not have to write YAML, learn the commands or know how the pipeline works. You
do that work. Ask them only for what you cannot find out yourself, in one short message.

## 1. Setup (once per machine)

1. Check whether it is already installed: `studio --version`. If that works, go to step 4.
2. Make sure `uv` is installed (`uv --version`). If it is not, install it:
   - Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
   - macOS and Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`

   Then open a new shell, or add the folder the installer names to `PATH`. If the person prefers
   pipx, `pipx install git+https://github.com/Maazsiddiqui01/demo-studio-oss` works the same way.
3. Install the CLI: `uv tool install git+https://github.com/Maazsiddiqui01/demo-studio-oss`
   (uv fetches a suitable Python, 3.10 or newer, if there is none).
4. Run `studio doctor --download`. It downloads the Chromium headless shell and the Kokoro voice
   model (about 350 MB, checked by SHA-256) into a cache once, and prints what is installed.
   On Linux, if Chromium cannot start because system libraries are missing, ask the person to
   install Playwright's system dependencies (they need sudo):
   https://playwright.dev/python/docs/browsers#install-system-dependencies
5. Claude Code only, optional: add the plugin so the `make-walkthrough` skill loads in later
   sessions: `claude plugin marketplace add Maazsiddiqui01/demo-studio-oss`, then
   `claude plugin install demo-studio@demo-studio-oss`. If you cannot run these, give the person
   the two `/plugin` commands from the README to type.
6. Tell the person it is ready, what you installed, and that they can now describe a video.

Nothing in the setup needs an API key, an account or a paid service.

## 2. Making a video

### What you need to know

Ask only for what is missing:

- **The app:** a URL (local or deployed), or the repo or folder and how to start it.
- **What to show:** the flows or features, in order.
- **Who will watch:** anyone (`mode: public`) or one client about their own system
  (`mode: handover`). If the app shows real customer data and the video is public, stop and ask
  for demo or seeded data, or build a small replica with made-up data.
- **Sign-in:** if the app needs one, the person runs `studio login <name>` and signs in themselves.
- **Format:** 16:9 by default. A square variant and burned-in subtitles suit social feeds, which
  autoplay muted. Most walkthroughs run 60 to 90 seconds.

### Steps

1. **Look at the app.** Start it if needed and keep it running. Open the pages you will show and
   note the controls for each flow. Pick stable selectors: `data-*` attributes first, then
   Playwright's role and text selectors (`role=button[name="Save"]`, `text=Save`). In an app you
   are working on, adding `data-demo="..."` attributes is fine if the person agrees.
2. **Write the storyboard yourself** as `walkthroughs/<name>.yaml` in the project. `studio init`
   writes a commented starter to copy from; every key is in `docs/storyboard-format.md`. For each
   step: one action, a caption title of three to five words with a short subtitle, and one or two
   short spoken sentences. About 150 to 200 words of narration make 60 to 90 seconds. Speed up long
   waits (`speed_up: true`), zoom on small controls (`zoom: auto`), and list in `sources:` where
   every claim comes from (the README, the docs, the app itself). Never invent numbers, customers
   or quotes.
3. **Pick the look.** `style.background: auto`, or a preset that suits the app's colours
   (`studio backgrounds` shows all 21). `theme: kinetic` for light apps and brands, `petrol` for
   dark. `studio slides walkthroughs/<name>.yaml` shows every intro, outro and caption design over
   the app. Use `viewport: auto` for the sharpest framed video.
4. **Render.** `studio validate walkthroughs/<name>.yaml`, then
   `studio render walkthroughs/<name>.yaml` (add `--variant square` when the storyboard has one).
5. **Review every frame yourself.** Open each image in `out/<name>/qa/sheets/` (handover videos:
   `out/clients/<client>/<name>/qa/sheets/`). Check that captions and subtitles are readable, rings
   and zoom land on the right elements, nothing secret shows, and a public video has no real names
   or contact details. Fix the storyboard and render again until it is right.
6. **Record the verdict:** `studio check out/<name> --frames pass --note "what you checked"`.
7. **Hand over:** give the person the MP4 path, the length and the gate result from
   `out/<name>/REPORT.md`. Offer `studio publish out/<name>` if they want a web page for it.

### Rules

- Never type a password and never ask the person to paste one. They sign in with `studio login`.
- On a live system, steps are read-only. A step that creates, edits, sends or deletes needs
  `live_write: true` and `confirmed_by_owner: true`, and the owner's yes comes from the person.
- Passwords, keys, tokens and card numbers are masked in the page before frames are captured. Add
  selectors for settings pages under `redact:`. Masking does not reach inside iframes.
- Keep the copy plain. The validator rejects em and en dashes and warns on hype words.
- Do not commit `out/` or saved sessions.

## 3. Reference

- [README](README.md): what it does and the options.
- [docs/prompts.md](docs/prompts.md): prompts people paste to ask for a video.
- [docs/storyboard-format.md](docs/storyboard-format.md): every storyboard key.
- [docs/modes-and-privacy.md](docs/modes-and-privacy.md): public and handover mode, sign-in, masking.
- [docs/quality-gate.md](docs/quality-gate.md): what the checks cover.
- [docs/publishing.md](docs/publishing.md): a folder or your own server.
