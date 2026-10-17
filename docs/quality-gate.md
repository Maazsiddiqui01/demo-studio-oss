# Quality gate

The gate decides whether a render is finished. It runs at the end of `studio render` and again
whenever you run `studio check <out-dir>`. It writes `qa/gate.json` and `REPORT.md` in the output
folder.

The video passes when six items are all PASS: frames, text scan, audio, file, delivery and server.
An item is PASS, FAIL or PENDING. PENDING means a person or a step has not done its part yet, and
it counts as not passed.

## The usual flow

```
studio render walkthrough.yaml
# open out/<name>/qa/sheets/ and qa/frames/ and look at every frame
studio check out/<name> --frames pass --note "14 frames checked, nothing wrong"
studio publish out/<name>
studio check out/<name> --cost "about 40 minutes of work"
```

- `studio render` always exits 0, even when the gate has not passed. After a render the frame
  review is always PENDING.
- `studio check` exits 0 only when every item passes, so use it in scripts.
- `studio check` runs the whole gate again, speech check included. Add `--no-speech` to skip that.
- `studio check` and `studio publish` work from any folder. `timeline.json` stores the storyboard
  path as an absolute path. The storyboard file has to stay at that path, because both commands
  read it again.
- `studio check` and `studio publish` find a variant again from `timeline.json`, and a cut-down by its
  `cutdown.name`.
- A new render deletes the saved frame verdict and `delivery.json`, so the frames item goes back to
  PENDING and the video counts as unpublished. Review and publish again.

## The items

### 1. Frames (a person decides)

`studio check` extracts one frame every 5 seconds from `video.mp4` into `qa/frames/` and builds
contact sheets of four frames each (two by two) in `qa/sheets/`. Look at every frame and check:

- captions are readable and not cut off
- the ring sits on the right element
- there are no layout glitches
- the intro and outro slides are correct
- public videos: no real names, no contact details, nothing from `banned_terms`
- handover videos: no visible password, key, token or payment detail

Record the verdict with `--frames pass` or `--frames fail`, and a note with `--note`. It is saved
in `qa/frames_verdict.json` with the time in UTC. Without a verdict the item is PENDING.

### 2. Text scan

- An em dash or en dash in any declared on-screen or spoken text is a hit, in both modes.
- Public mode only: the text collected from every screen during recording (page title, visible
  text, input values, `placeholder`, `title` and `alt` attributes, one snapshot per step plus
  intro and outro) is scanned for banned terms and contact details, and the declared texts are
  scanned for banned terms.

PASS means no hits. The result also lists how many screens were scanned, how many elements the
secret patterns blurred, and which steps had masked text. Each blurred element is counted once,
under the step during which it was first blurred, so the counts are per step and do not add up as
the video goes on. Those numbers are for your information and never fail the item.

### 3. Audio

- **Timing.** Each narration line must start and end inside its own step, with 0.01 s of slack.
- **Peak.** The loudest sample of the final mix in `video.mp4` (voice plus music, after AAC
  encoding) must be below -1 dB.
- **Silence.** In `narration.wav`, the voice alone, any silence of 3 s or more (below -45 dB) is
  measured. Time inside the intro and outro slides does not count. A gap with more than 3 s left is
  a failure. Measuring the voice alone means the music bed cannot hide a gap. To fix a gap, add
  narration or shorten the stretch (a higher `speed_factor` on a sped-up wait).
- **Speech check (optional).** With the `check` extra installed (see the README), faster-whisper
  (`base.en`, on the CPU) transcribes `narration.wav`. The text is compared word by word with the
  script. A similarity below 0.85 fails the item. Without faster-whisper the check is skipped and
  does not affect the result. faster-whisper downloads its model on first use.

### 4. File

All of these must hold:

- video codec is H.264 and audio codec is AAC
- picture size is the canvas size when framed, the viewport size when not
- the file is faststart (the index sits before the media data, so it plays while it downloads)
- the duration is within 5 percent of the timeline total
- `poster.jpg` exists
- `captions.vtt` parses: it starts with `WEBVTT`, every cue has a timing line, ends after it starts,
  and cues are in order

### 5. Delivery

- **After `studio publish`:** the result in `delivery.json`.
  - Public on a server with a `base_url`: the page, video, captions and poster return 200, a range
    request for the video returns 206, and the video is `video/mp4`. The URL checks also run for a
    folder target when `publish.check_urls` is true. A folder target without checks passes when the
    three files exist.
  - Private link: no password returns 401, a wrong password returns 401, the right password returns
    200 for the page and video and 206 for a range request, and every response carries `noindex`.
- **`local_only: true`** in `delivery` counts as done: you deliver the MP4 yourself.
- **Neither:** PENDING, "not published yet".

### 6. Server

Off by default, and then it passes with a note. It applies only when `publish.host_check` is true in
your settings and the video went to an ssh server. The gate then reads `vps_check.json` from the
root of your output folder (`out/`, or `DEMO_STUDIO_OUT`). You write that file: a JSON object with
`"ok": true` or `"ok": false`, for example after comparing the server's running containers and
timers with a snapshot taken before you published. If the file is missing the item is PENDING.

### Cost

`--cost "text"` on `render` or `check` is copied into the report. It never affects the result.
Without it the report says "not recorded".

## What is in REPORT.md

`out/<name>/REPORT.md` is rewritten on every gate run. It holds:

- the mode (and client folder for handover), the storyboard file, the time checked and the verdict
- a table of durations: intro slide, each step, outro slide, with start, end, length and narration length
- the total length, captured frame count, caption cue count and the narration gain applied
- a Masked section: which elements the secret patterns blurred, per step
- the Sources you declared
- the gate items 1 to 6 with PASS, FAIL or PENDING and the numbers behind each, then item 7, the cost

The same data is in `qa/gate.json` for scripts.
