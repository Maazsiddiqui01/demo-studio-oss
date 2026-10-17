# How it works

`studio render walkthrough.yaml` runs five stages in order. `studio publish` is a separate sixth.

| Command | What it does |
|---|---|
| `studio init [folder]` | Writes a starter storyboard and a tiny demo app. |
| `studio doctor [--download]` | Checks ffmpeg, the browser, the voice and the workspace. `--download` fetches the browser and voice model now. |
| `studio validate <file> [--variant NAME]` | Checks a storyboard, and each of its variants unless you name one. |
| `studio slides <file> [--variant NAME] [--out DIR]` | Writes stills of every intro layout, outro layout and caption style over your app, to pick a look before rendering. |
| `studio backgrounds [--out FILE]` | Writes one image with every wallpaper preset, labelled by name and category. |
| `studio render <file>` | Narrate, record, assemble, gate. Flags: `--variant NAME`, `--headed` (watch the browser), `--keep-frames`, `--no-cut`, `--cut-only`, `--no-speech`, `--reassemble` (encode again from a kept recording, without recording), `--cost "..."`. |
| `studio check <out-dir>` | Runs the gate again. Records the frame review with `--frames pass --note "..."`. |
| `studio login <name>` / `logout <name>` | Saves or deletes a sign-in session ([modes-and-privacy.md](modes-and-privacy.md)). |
| `studio publish <out-dir>` | Sends the render to a folder or server ([publishing.md](publishing.md)). |
| `studio serve <folder> [--port 5173]` | Previews a demo app, with client-side routes working. |
| `studio windows` / `studio inspect <title>` | Desktop driver: lists the open windows, or one window's controls with a selector for each ([desktop.md](desktop.md)). |
| `studio expire [--dry-run]` | Deletes expired private links (on the server). |

## The stages

1. **Validate.** The storyboard is loaded and every rule in
   [storyboard-format.md](storyboard-format.md) is checked. Nothing is written. Errors stop the render.
2. **Narrate.** Kokoro-82M speaks each narration line (intro, each step, outro) and the audio is
   trimmed of leading and trailing silence. A line is cached by backend, voice, speed and text, so
   unchanged lines are not spoken again. Makes `audio/<line>.wav` and `narration.json`.
3. **Record.** Playwright opens the app in Chromium (1x scale, light colour scheme, English locale,
   scrollbars hidden) and a script is injected before the app's own scripts. It draws the intro and
   outro slides, the numbered caption, the ring, the cursor and the "Sped up" badge, and it blurs
   secrets. The slides and captions use bundled fonts (Inter, Archivo, Mona Sans and JetBrains Mono,
   all SIL OFL), so they look the same on every machine. The recorder runs the steps and grabs JPEG
   frames (quality 92) from Chromium's screencast with the browser's own timestamps. It also
   collects each screen's visible text for the gate.
   Makes `frames/`, `timeline.json`, `strings.json`, `masked.json`.
   With `driver: desktop` this stage drives a Windows app through UI Automation instead, records
   its part of the screen with ffmpeg, and draws the same overlays afterwards ([desktop.md](desktop.md)).
4. **Assemble.** ffmpeg turns the frames, the narration, the optional music and the optional
   burned-in subtitles into the final files. The video is H.264 (x264, preset slow, CRF 18) at 30
   fps with AAC audio at 160 kbps, and the index is moved to the front so it plays while it
   downloads. Makes `narration.wav`, `mix.wav`, `captions.vtt`, `video.mp4`, `poster.jpg`,
   `timeline_out.json`. The temporary `frames/` and `subs/` folders are deleted unless you pass
   `--keep-frames`.
5. **Gate.** The checks in [quality-gate.md](quality-gate.md). Makes `qa/` and `REPORT.md`.
6. **Publish.** `studio publish`. Makes `delivery.json`, and `PRIVATE_LINK.txt` for a private link.

Public videos go to `out/<name>/`. Handover videos go to `out/clients/<client>/<name>/`, with a
`RETENTION.md` beside them. With a `cutdown`, a second video is rendered into `out/<cutdown name>/`.
A variant renders into `out/<name>-<variant>/`.

| File in the output folder | Holds |
|---|---|
| `audio/*.wav`, `narration.json` | One WAV per line, and its path, length and text. |
| `timeline.json` | Wall-clock marks for each slide and step, the sped-up wait windows, every frame's time and file number, and the absolute storyboard path and variant. |
| `strings.json` | The visible text of each screen. Pattern matches are replaced by `[masked]`. |
| `masked.json` | Elements the secret patterns blurred, each reported once. |
| `narration.wav` | The voice alone, on the final timeline. |
| `mix.wav` | Voice plus music. Only when `style.music` is set. |
| `captions.vtt` | WebVTT captions made from the narration text. |
| `video.mp4`, `poster.jpg` | The video (H.264, AAC, faststart) and the poster frame. |
| `timeline_out.json` | The final timeline: segments, audio gain, cue count, picture size, frame layout and whether subtitles are burned in. |
| `qa/`, `REPORT.md` | Contact sheets, the frame verdict, `gate.json`, and the report. |

## Timing and sped-up waits

A step lasts at least 0.35 s, then its narration, then 0.7 s, plus `hold`. The recorder measures
that in output time, so a sped-up wait counts for less than it takes in real time. The intro slide
shows for at least 3.5 s and the outro slide for at least 4.5 s.

Real time and video time differ only inside sped-up waits. `Clock` in `assemble.py` maps one to the
other: output time is real time minus, for each wait window, the overlap times `1 - 1/factor`. A
40 s wait at 4x counts as 10 s. Two things use this one clock:

- **Frames.** Each frame is shown for the clock difference to the next frame, so frames inside a
  wait play `factor` times shorter. ffmpeg reads them from a concat list with those durations and
  resamples to 30 fps.
- **Narration.** Each line starts 0.35 s after its step starts on the same clock (the outro line
  starts 0.6 s later, after the slide fades in).

So picture and voice cannot drift apart. The voice is mixed to one track and set to a peak of
-2.5 dBFS. With music, the bed is added and the whole mix is held below -1.5 dBFS. Captions come
from the narration: sentences, with sentences over 90 characters split at commas, timed in
proportion to their length across the span of the line.

## Why frames are captured at the viewport size

Chromium's screencast is capped at the viewport's size in CSS pixels. Asking for a larger frame
does not add detail. So the viewport is the true resolution of the recording. The framed look
always fills the frame: the window reaches the padding line, so the wallpaper stays a thin margin.
`viewport: auto` sizes the browser so that this happens at exactly 1:1, the sharpest result. A
recording that is smaller than the space (a desktop window, a small fixed viewport) is scaled up
to fill it, up to 2x (`style.fill: auto`); `fill: false` keeps it at 1:1 with more wallpaper. A
larger one is scaled down, and the assembler logs a tip with a viewport that would fit 1:1.

## The framed look

With `style.frame` on, the recording sits in a rounded window on a wallpaper. Three images make the
frame, all drawn by screenshotting small HTML pages with Playwright, so no image library is needed:

| Image | Holds |
|---|---|
| `wallpaper.png` | The background. With `motion: drift` it is 6 percent larger than the canvas on each side, so it has room to pan. A little fine grain stops gradients from banding after H.264 encoding. |
| `window.png` | The window's shadow, optional border and optional title bar, on transparency. |
| `mask.png` | A white rounded rectangle the size of the recording. `corners: squircle` draws it with the CSS `corner-shape` property. |

The three images are cached (in `frames/` inside the cache folder), keyed by the layout and the
page contents, so a render only redraws them when the look changes.

ffmpeg builds the frame in one filter graph. It crops the wallpaper to the canvas with x and y as
functions of time, so the wallpaper drifts: a slow sine in each axis, with cycles of 23 s and 31 s.
It lays the window layer on that, scales the recording to its slot, merges the mask into the
recording as its alpha channel, and overlays the result. Only the crop, overlay and alphamerge
filters are used, so ffmpeg 4.4 works as well as a current build.

## Subtitles

With `style.subtitles`, the narration is burned into the picture. The cues are the ones in
`captions.vtt`. Each cue is drawn as a transparent PNG, by screenshotting a small HTML page with
the bundled Mona Sans font. The PNGs play as one image track: an ffconcat list gives each image its
exact cue time, with a blank image in the gaps, and ffmpeg overlays that track on the video. This
needs only the overlay filter, so no ffmpeg build with libass or freetype is required. A framed
video shows the cues on the wallpaper in a band below the window, which the layout reserves.
An unframed video shows them above the caption. The PNGs and the list are temporary files.

## Music

With `style.music: ambient`, a quiet pad is synthesised on your machine from four slow chords of
eight seconds each, crossfaded, with a short reverb. A file path (WAV, FLAC or OGG) is used instead
when you give one: it is looped or cut to length and fades out at the end. Either way the music is
set to `music_db` (RMS dBFS) between narration lines.

Under narration it ducks by `duck_db`. The ducking curve is a gain in dB that is 0 between lines
and `-duck_db` while a line plays. It starts to dip a moment before a line begins and recovers a
moment after it ends, with smooth ramps. The curve is worked out at 100 Hz and interpolated to the
audio sample rate, which keeps it fast for long videos. The narration spans come from the same
timeline as the captions, so the music dips where the voice is.

## How zoom works

Zoom is a CSS transform on `document.body`: a translate and a scale from the top-left corner, eased
over 750 ms. The overlay lives outside `body` (as a child of `html`), so captions, ring and cursor
stay at normal size, and the ring reads its element's position again on every animation frame. The
zoomed window is clamped to the original viewport, so no empty edge shows, and the scale is lowered
if the element would not fit.

## Known limits

- **Masking has gaps.** The masking script runs in the top page only. It does not reach inside
  iframes or shadow DOM, open or closed, and it cannot see text inside images, canvas or video.
  Review the frames ([quality-gate.md](quality-gate.md)) before you share a video.
- **Zoom can look off on some pages.** Because zoom is a transform on `document.body`,
  `position: fixed` elements and pages scrolled at the window level can look wrong while zoomed. The
  page scales as one block, so fixed headers and sidebars move with it, and scrolling the window
  while zoomed is not compensated. If a step looks wrong, scroll first and zoom after, or leave zoom
  off for that page.
- **The recording is capped at the viewport size.** Screencast frames never exceed the viewport in
  CSS pixels, so a bigger canvas does not add detail. Use `viewport: auto` for sharp text at 1:1.
  Scaling a smaller recording up to fill the frame, or a larger one down, softens text a little.
- **ffmpeg can hang.** ffmpeg 7 and 8 sometimes deadlock at the end of a long filter graph when
  the machine is busy. Every ffmpeg run is watched: one that makes no progress for 3 minutes is
  stopped and tried once more with single-threaded filtering.
- **Fixed browser settings.** Apps are recorded in Chromium with the light colour scheme and the
  `en-US` locale, at 1x scale, and the video is 30 fps.

## Where things live

| Module in `demo_studio/` | Role |
|---|---|
| `cli.py`, `scaffold.py`, `doctor.py` | The `studio` command, `studio init`, `studio doctor`. |
| `storyboard.py`, `textscan.py` | Loading and validating storyboards, and the dash, hype, banned-term and contact scans. |
| `tts.py` | Kokoro narration, the model download and the line cache. |
| `record.py`, `overlay.js`, `templates/titles/overlay.css` | The Playwright driver, and the overlay it injects: slides, captions, ring, cursor, masking, zoom. |
| `assemble.py` | The clock, the frame list, the audio mix, captions and the ffmpeg run. |
| `style.py`, `music.py`, `subtitles.py` | The framed look, the music bed, burned-in subtitles. |
| `gate.py` | The checks and `REPORT.md`. |
| `publish.py`, `serve.py`, `expire.py` | Publishing, the local demo-app server, expiring private links. |
| `preview.py` | `studio slides` and `studio backgrounds`. |
| `session.py`, `config.py`, `tools.py` | Saved sign-in sessions, paths and settings, ffmpeg and Chromium. |

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `DEMO_STUDIO_HOME` | the current folder | The workspace: `demo-studio.yaml`, `out/`, and where `studio login` and `serve` look. On a server, `expire.py` reads it as the site root. |
| `DEMO_STUDIO_OUT` | `<workspace>/out` | Where renders are written. |
| `DEMO_STUDIO_CACHE` | platform cache folder | Voice models, narration cache, frame assets. |
| `DEMO_STUDIO_TTS` | auto | `kokoro` (torch) or `kokoro-onnx` (CPU). Any other value acts as `kokoro-onnx`. |
| `DEMO_STUDIO_KOKORO_ONNX_DIR` | `<cache>/models` | Folder for the voice model files. |
| `DEMO_STUDIO_FFMPEG` | `ffmpeg` on the path | Path to an ffmpeg program. If none is found, the copy bundled with `imageio-ffmpeg` is used. |
| `DEMO_STUDIO_CADDY_CONTAINER` | `demo-studio-web` | Server only, for `expire.py`. |

Without `DEMO_STUDIO_TTS`, the torch backend is used when the `kokoro` package is installed (the
`gpu` extra, which runs on CUDA when a GPU is available), otherwise the CPU backend.

| Folder | Windows | macOS | Linux |
|---|---|---|---|
| Cache | `%LOCALAPPDATA%\demo-studio\cache` | `~/Library/Caches/demo-studio` | `$XDG_CACHE_HOME/demo-studio` (default `~/.cache/demo-studio`) |
| Sessions | `%LOCALAPPDATA%\demo-studio\auth` | `~/Library/Application Support/demo-studio/auth` | `$XDG_DATA_HOME/demo-studio/auth` (default `~/.local/share/demo-studio/auth`) |
| User settings | `%APPDATA%\demo-studio\config.yaml` | `~/.config/demo-studio/config.yaml` | `$XDG_CONFIG_HOME/demo-studio/config.yaml` |

## The cache and first-run downloads

The cache folder holds `models/` (the voice model), `tts/` (spoken lines) and `frames/` (the
wallpaper, window and mask images). It is safe to delete: it refills on the next render.

The first render downloads what it needs, once. `studio doctor --download` fetches the first two
ahead of time.

- **Chromium.** Playwright installs the headless shell (about 100 to 170 MB) into its own browser
  folder. `studio login` needs the full Chromium and installs it the first time you sign in.
- **Voice model.** On the CPU backend, `kokoro-v1.0.onnx` and `voices-v1.0.bin` (about 350 MB in
  all) come from the kokoro-onnx GitHub releases. Each file is written to a `.part` file, checked
  against a built-in SHA-256, and only then moved into place. A mismatch deletes it and stops.
- **Other models.** The torch backend downloads Kokoro-82M from Hugging Face on first use, and
  faster-whisper downloads its `base.en` model the first time the speech check runs.

Kokoro-82M is licensed under Apache-2.0. If you use the videos commercially, do not swap in a voice
model with a non-commercial licence.
