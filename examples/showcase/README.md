# The showcase

A video about demo-studio, made by demo-studio. Nobody recorded the screen. The storyboard drives a
small web app in this folder, and a local voice reads the script.

The video has nine steps: the hook, the storyboard, one command, the result, the quality gate, the
two modes, what it is for, the licence, and the install command.

## Render it

Install demo-studio (see the [README](../../README.md#quick-start)), then run these from the
repository root:

```bash
studio render examples/showcase/showcase.yaml                    # 1920x1080
studio render examples/showcase/showcase.yaml --variant square   # 1080x1080 for social feeds
```

The first command writes `out/demo-studio-showcase/`. The second writes
`out/demo-studio-showcase-square/`. Both folders hold `video.mp4`, `captions.vtt`, `poster.jpg`,
`REPORT.md` and the contact sheets in `qa/sheets/`.

You do not need to start a server. The storyboard sets `serve: "."`, so demo-studio serves this
folder at `http://localhost:5207` for the length of the render. Keep that port free.

How the storyboard is set up:

- The app is one page, `index.html`, whose scenes are client-side routes, so the storyboard uses
  `navigation: spa`.
- `viewport: auto` sizes the browser to fill the canvas at 1:1. The app scales its 1440-wide design
  to fit.
- The look is `lagoon` wallpaper, the light `kinetic` theme, `card` captions, burned-in subtitles
  and an ambient music bed.
- The `square` variant has its own viewport, a 1080 by 1080 canvas, more padding and the `ocean`
  wallpaper. The steps stay the same.

## What is real on screen

Every artifact the video shows is real. They all come from one render of the starter project that
`studio init` writes:

- `assets/artifacts.js` holds the starter storyboard, the log of that render with its real
  timings, the results of its quality gate, and the message `studio validate` prints when a banned
  term appears in a public video's title. The terminal scene replays the log at its real pace.
- `assets/tidy-tour.webm` is a clip of the video that render produced.
- `assets/sheet.jpg` is that render's contact sheet, and `assets/poster.jpg` is its poster frame.

The log was captured with the CPU voice, and the narration of the one-command step says so.

## Rebuild the assets

Do this when the starter changes, so the video keeps showing what the tool does today.

1. In an empty folder, run `studio init`, then `studio render walkthrough.yaml`. Keep the console
   output of the render, with the time of each line.
2. Open the contact sheets in `out/tidy-tasks-tour/qa/sheets/` and review the frames. Record the
   verdict with `studio check out/tidy-tasks-tour --frames pass --note "..."`. Run
   `studio publish out/tidy-tasks-tour` so that the delivery item has a result too.
3. Put the starter storyboard, the timed log lines and the gate results into `assets/artifacts.js`.
   The file sets `window.ARTIFACTS` with four keys: `log` (the command, the total seconds and a
   list of `[seconds, text]` lines), `storyboard` (the YAML as text), `banned` (the validator's
   output as a list of lines) and `gate` (whether it passed, the video length and size, the cue
   count, and a list of `[name, passed, note]` items).
4. Cut a short clip of `video.mp4` with ffmpeg and save it as `assets/tidy-tour.webm`. Copy a
   contact sheet to `assets/sheet.jpg` and `poster.jpg` to `assets/poster.jpg`.
5. Render the showcase again. The terminal scene replays the new log, and the quality gate scene
   shows the new gate items and the banned-term message.
