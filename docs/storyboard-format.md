# Storyboard format

A storyboard is one YAML file. It lists the steps of a walkthrough, the words spoken at each step,
and a few settings. `studio render <file>` turns it into a narrated MP4.

Run `studio init` to get a starter storyboard and a small demo app. Run `studio validate <file>`
to check a storyboard without rendering. Validation prints every problem at once and exits with
status 2 when there are any. When the storyboard is valid it prints `OK`, any warnings, and for a
framed video the wallpaper it picked.

## An annotated example

This is a complete public-mode storyboard for the starter app. It shows the main top-level keys.

```yaml
version: 1                          # always 1
name: tidy-tasks-tour               # output folder (out/tidy-tasks-tour/) and the slug when published
mode: public                        # public or handover. Required.
title: "Plan a day in *Tidy Tasks*" # intro slide title. Required. *Words* go on the highlight block.
eyebrow: "ACME DEMOS"               # small uppercase line above the title
intro_note: "A made-up demo app. The waiting time is sped up."   # intro slide, under the title

intro:
  layout: auto                      # statement | product | agenda | cinematic | auto
  narration: "This is a short tour of Tidy Tasks, a small demo app with made-up data."
outro:
  layout: summary                   # summary | cta | cinematic | auto
  heading: "That is the *whole tour*"   # text in asterisks goes on the highlight block
  bullets: ["Add a task in one line", "Plan my day puts what is due first"]
  # cta: "github.com/you/your-app"  # a link or command shown on the slide (layout cta)
  narration: "That is the tour. Thanks for watching."

base_url: "http://localhost:5199"   # where the app runs. Required.
serve: demo-app                     # optional: serve this folder at base_url while recording
navigation: load                    # load (full page loads) or spa (client-side routes)
voice: "af_heart"                   # a Kokoro voice id
speed: 1.0                          # narration speed, 1.0 is normal
viewport: [1440, 900]               # browser size in CSS pixels, or auto
poster: "result@1.5"                # intro | <step id> | <step id>@<seconds into the step>

sources:                            # where each claim in the narration comes from. Required.
  - "demo-app/index.html (made-up demo data)"

banned_terms: ["Initech"]           # public mode: words that must never appear on screen or in the voice
allowed_hosts: []                   # public mode: hosts the contact scan lets through
redact:                             # blurred in addition to the built-in secret rules
  selectors: [".account-number"]
  patterns: ['\bORD-\d{8}\b']

style:                              # the framed look. On by default in public mode.
  frame: true
  canvas: [1920, 1080]
  background: aurora                # a preset, a category, auto, a list of presets, CSS, or an image path
  padding: 0.04                     # space around the window, as a fraction of the shorter canvas side
  radius: 18
  corners: squircle                 # squircle | round
  border: false                     # a thin light border around the window
  fill: false                       # scale a smaller recording up to fill the space
  motion: drift                     # drift (the wallpaper pans slowly) | none
  shadow: true
  chrome: true                      # a window bar with three dots
  chrome_title: "Tidy Tasks"
  theme: petrol                     # petrol | kinetic | navy: slides, captions and ring
  accent: "#FF5A1F"                 # optional: replaces the theme's accent and ring colour
  captions: card                    # card | pill | lower
  # subtitles: true                 # burn the narration into the picture, for muted feeds
  zoom: auto                        # default zoom for click, type and hover steps
  music: ambient                    # ambient, a file path, or off
  music_db: -28
  duck_db: 8

delivery: { public: true, private_link: false, expires: null, local_only: false }

cutdown:                            # an optional shorter edit, rendered as its own video
  name: tidy-tasks-short
  steps: [type, add, plan]
  title: "Plan a day, fast"
  intro_narration: "Here is the short version."
  outro: { heading: "Short version", bullets: ["Type it", "Plan it"], narration: "That is it." }
  poster: plan
  overrides:
    plan:
      narration: "Plan my day sorts the list. The wait is sped up."
      caption: { title: "Plan my day", sub: "Sorted for you" }

steps:
  - id: list
    route: "/"
    action: wait_for
    target: "[data-demo=list]"
    caption: { n: 1, title: "Today's list", sub: "Four tasks, one due today" }
    narration: "Here is today's list. One task is due today."
  - id: type
    action: type
    target: "[data-demo=new-task]"
    text: "Book the team retro"
    zoom: auto
    caption: { n: 2, title: "Add a task", sub: "Type it in one line" }
    narration: "To add a task, type it in one line."
  - id: add
    action: click
    target: "[data-demo=add]"
    caption: { n: 3, title: "Save it", sub: "It joins the list" }
    narration: "Add puts it at the end of the list."
  - id: plan
    action: click
    target: "[data-demo=plan]"
    wait_for: "[data-demo=plan-result]"
    speed_up: true
    speed_factor: 4
    timeout: 120
    caption: { n: 4, title: "Plan my day", sub: "The list is sorted for you" }
    narration: "Plan my day sorts the list. The wait is sped up, and the video says so."
  - id: result
    action: pause
    highlight: "[data-demo=plan-result]"
    zoom: 1.4
    zoom_on: "[data-demo=plan-result]"
    hold: 0.6
    caption: { n: 5, title: "The plan", sub: "What is due comes first" }
    narration: "The plan starts with the invoices, because they are due today."
```

Handover mode uses the same format with a few different rules. A minimal handover header:

```yaml
mode: handover
client: acme                        # folder-safe slug: out/clients/acme/<name>/
auth: acme-crm                      # a session saved by `studio login acme-crm`
login_url: "https://app.example.com/login"
base_url: "https://app.example.com"
delivery: { public: false, private_link: false, local_only: true }
```

See [modes-and-privacy.md](modes-and-privacy.md) for what each mode allows.

## Top-level keys

Unknown top-level keys are ignored, not reported. A typo in a key name does nothing, so run
`studio validate` and read the result.

| Key | Type | Default | What it does |
|---|---|---|---|
| `version` | integer | required | Must be `1`. |
| `name` | string | required | Output folder and publish slug. Lowercase letters, digits and dashes, 2 to 63 characters, starting with a letter or digit. |
| `mode` | string | required | `public` or `handover`. |
| `title` | string | required | Intro slide title. `*Words*` in asterisks go on the highlight block. |
| `eyebrow` | string | empty | Small uppercase line on the intro and outro slides. |
| `intro_note` | string | none | Line under the intro title. Also used as the page description when published. |
| `intro.narration` | string | none | Spoken over the intro slide. |
| `intro.layout` | string | `auto` | `statement`, `product`, `agenda`, `cinematic` or `auto`. See Slides. |
| `outro.heading` | string | empty | Heading of the outro slide. Asterisks work here too. |
| `outro.bullets` | list of strings | empty | Bullets on the outro slide. |
| `outro.narration` | string | none | Spoken over the outro slide. |
| `outro.cta` | string | none | A link or command shown as a call to action on the outro slide. |
| `outro.layout` | string | `auto` | `summary`, `cta`, `cinematic` or `auto`. `cta` needs `outro.cta`. See Slides. |
| `base_url` | string | required | Where the app runs. A trailing slash is removed. A value starting with `TODO` counts as missing. |
| `serve` | path | none | A folder with an `index.html`, served at `base_url` while recording. Details below. |
| `navigation` | string | `load` | `load` or `spa`. Details below. |
| `voice` | string or list | `af_heart` | `female`, `male`, `auto` (either), a list of voice ids, or one id such as `af_heart`, `am_michael`, `bf_emma` or `bm_george`. `female`, `male`, `auto` and lists pick one voice from the video's name, so videos differ and a re-render keeps its voice. See "Voices" below. |
| `speed` | number | `1.0` | Speaking speed of the voice. It does not change the video speed. |
| `viewport` | `[width, height]` or `auto` | `[1440, 900]` | Browser size in CSS pixels. Frames are captured at this size. `auto` fills the canvas at 1:1. Details below. |
| `poster` | string | `intro` | Which moment becomes `poster.jpg`. Details below. |
| `sources` | list of strings | required | Where each factual claim in the narration comes from. Shown in `REPORT.md`. An entry starting with `TODO` counts as missing. |
| `client` | string | none | Handover only, required there. A folder-safe slug. |
| `auth` | string | none | Name of a saved sign-in session (`studio login <name>`). |
| `login_url` | string | none | Where `studio login` opens. Falls back to `base_url`. |
| `seeded_test_data` | boolean | `false` | Public mode only: declares that the app behind `auth` holds made-up data. This is what allows `auth` in public mode. |
| `local_copy` | boolean | `false` | Handover only: the app is a private copy on this machine with made-up data. Details below. |
| `banned_terms` | list of strings | empty | Public mode: words that must not appear on screen or in the narration. Case-insensitive. |
| `allowed_hosts` | list of strings | empty | Public mode: hosts the contact scan lets through. Matched as a substring of the URL. |
| `redact.selectors` | list of CSS selectors | empty | Extra elements to blur. Added to the built-in list. |
| `redact.patterns` | list of regular expressions | empty | Extra text patterns to blur. Added to the built-in list. |
| `delivery` | mapping | empty | How the video is delivered. Details below. |
| `cutdown` | mapping | none | A shorter edit rendered as its own video. Public mode only. Details below. |
| `variants` | mapping | none | The same steps with other settings, such as a square canvas. Rendered with `--variant`. Details below. |
| `style` | mapping | see below | The framed look, theme, captions, subtitles, zoom and music. |
| `steps` | list | required | At least one step. |

### delivery

| Key | Default | Meaning |
|---|---|---|
| `public` | `false` | Public mode: `studio publish` uploads the video to your site. Handover mode: must be false. |
| `private_link` | `false` | Handover mode: `studio publish` creates a private link on your server. An error in public mode. |
| `expires` | none | Date as `YYYY-MM-DD`. Required when `private_link` is true. |
| `local_only` | `false` | You will deliver the MP4 yourself. The gate then counts delivery as done without a publish step. |

A handover video with `private_link: false` stays on your machine. If `local_only` is not set, run
`studio publish` once: it records "local only" and the gate then counts delivery as done.

### redact

`redact.selectors` take CSS selectors. `redact.patterns` take regular expressions. Both lists are
added to the built-in rules (see [modes-and-privacy.md](modes-and-privacy.md)). The validator
compiles each pattern with Python's `re`, but the browser runs it as a JavaScript `RegExp`
without regard to case. Write patterns that mean the same in both, and avoid Python-only syntax
such as `(?P<name>...)`. A pattern the browser cannot compile is dropped silently.

### serve

`serve: demo-app` serves that folder on the local machine only (loopback), at the port in `base_url`
(port 80 when none), for the length of the render. The folder is looked up next to the storyboard
first, then in the workspace, and must contain `index.html`. A path that does not exist falls back
to `index.html`, so client-side routes load. `base_url` must use `localhost` or the IPv4 loopback
address. Remove `serve` when the app runs somewhere else.

### navigation

`load` opens each new route with a full page load. `spa` opens the first route with a page load
and moves to later routes with the browser history API, without reloading, which suits apps with
client-side routing.

### viewport

The default is `[1440, 900]`. Chromium captures frames at the viewport size, so the viewport is the
true resolution of the recording (see [how-it-works.md](how-it-works.md)).

`viewport: auto` sizes the browser to fill the canvas at 1:1. It takes the canvas minus the padding,
and minus the window bar and the subtitle band when those are on, and rounds down to even numbers.
On the default canvas and padding that is 1832 by 992. A variant can set its own `canvas` and
`viewport: auto` follows it. `auto` needs a framed video: with `frame: false` it falls back to
1440 by 900.

### poster

`intro` takes the frame just before the intro slide ends. A step id such as `result` takes the
frame 0.6 s before that step ends. `result@1.5` takes the frame 1.5 s into that step. The time is
kept inside the step. An id that matches no step falls back to the first step without an error.

### local_copy

For a handover video recorded against a private copy of the app on your own machine, filled with
made-up data. `base_url` must then be `localhost` or a loopback address. No live system is
touched, so `auth` may be empty and form steps need no `live_write`. Say so in `intro_note`.

## Steps

Each step is a mapping. The recorder runs the steps in order. A step stays on screen for at least
0.35 s, plus the length of its narration, plus 0.7 s, plus `hold`. Narration length therefore sets
the pace of the video.

| Key | Type | Default | What it does |
|---|---|---|---|
| `id` | string | required | Unique name of the step. Used for the narration file, `poster`, `cutdown.steps` and `cutdown.overrides`. |
| `action` | string | required | One of `click`, `type`, `hover`, `wait_for`, `scroll`, `goto`, `pause`. |
| `caption.title` | string | required | Main line of the caption. |
| `caption.sub` | string | empty | Smaller line under the title. `(sped up)` is added when `speed_up` is true. |
| `caption.n` | integer | position of the step | The step number shown in the caption. If you set it, numbers must run 1, 2, 3 and so on in order. |
| `narration` | string | required | The spoken line. |
| `route` | string | none | Path joined to `base_url`, or a full URL, opened before the step when it differs from the current page. |
| `target` | selector | none | Playwright selector of the element to act on. Required for `click`, `type`, `hover`, `wait_for`. The first match is used. |
| `text` | string | none | What to type. Required for `type`. Typed at 55 ms per key. |
| `wait_for` | selector | none | After the action, wait until this element is visible. |
| `timeout` | seconds | 30 (120 with `speed_up`) | How long `wait_for` and `highlight` may wait for their element. |
| `highlight` | selector | none | Draws the highlight ring on this element for the whole step. |
| `speed_up` | boolean | `false` | Plays the wait faster and labels it. Needs a wait (see rules). |
| `speed_factor` | number | `4.0` | How many times faster the wait plays. At least 1. |
| `hold` | seconds | `0` | Extra time on the step after the narration ends. |
| `scroll_by` | integer | `0` | For `scroll` without a `target`: pixels to scroll. 0 means 500. |
| `zoom` | see Zoom | off | Zoom for this step. |
| `zoom_on` | selector | none | Element to zoom to. Defaults to `target`, then `highlight`. |
| `voice` | string | the video's voice | This step's narrator: an id, `female` or `male`. Use it for two narrators in one video. |
| `live_write` | boolean | `false` | Declares that the step creates, edits, sends or deletes data. |
| `confirmed_by_owner` | boolean | `false` | The owner of the system agreed to that write. Required with `live_write`. |

Unknown step keys are ignored, not reported.

### Actions

| Action | What it does |
|---|---|
| `click` | Moves the cursor to `target`, rings it, then clicks. |
| `type` | Does what `click` does, then types `text`. |
| `hover` | Moves the cursor to `target` and rests there. No click. |
| `wait_for` | Waits until `target` is visible. Pair it with `speed_up` for slow jobs. |
| `scroll` | With `target`: scrolls it to the middle of the window. Without: scrolls `scroll_by` pixels. |
| `goto` | Does nothing itself. The step's `route` does the navigation. |
| `pause` | Does nothing. Holds the step so the narration can play. Use it with `highlight` or `zoom`. |

The page the recording starts on is the `route` of the first step that has one, or `/` when no
step has a route. It loads before the intro slide appears.

### Speeding up waits

Set `speed_up: true` on a step that waits (action `wait_for`, or any step with a `wait_for`
selector). While it waits, a "Sped up 4x" badge shows in the corner, the caption gets
"(sped up)", and that stretch of video plays `speed_factor` times faster. The narration still
plays at normal speed, so write enough words to cover the sped-up stretch: the gate reports any
silence over 3 s.

## Voices

The narration uses Kokoro-82M on your machine. `female`, `male` and `auto` pick from the clearest
voices of each kind:

| Pool | Voices |
|---|---|
| `female` | `af_heart`, `af_bella`, `bf_emma` |
| `male` | `am_michael`, `am_fenrir`, `bm_george`, `am_puck` |

Any English Kokoro voice id also works: `af_alloy`, `af_aoede`, `af_bella`, `af_heart`,
`af_jessica`, `af_kore`, `af_nicole`, `af_nova`, `af_river`, `af_sarah`, `af_sky`, `am_adam`,
`am_echo`, `am_eric`, `am_fenrir`, `am_liam`, `am_michael`, `am_onyx`, `am_puck`, `am_santa`,
`bf_alice`, `bf_emma`, `bf_isabella`, `bf_lily`, `bm_daniel`, `bm_fable`, `bm_george`, `bm_lewis`.
The first letter is the accent (`a` American, `b` British), the second the voice (`f` female,
`m` male). A step can set its own `voice` for a second narrator.

## Slides

The video opens on an intro slide and closes on an outro slide. The intro shows for at least 3.5 s
and the outro for at least 4.5 s, or as long as their narration needs. Both are drawn in the same
browser as the app. To see every intro layout, outro layout and caption style over your own app
before you render, in the storyboard's theme, run `studio slides walkthrough.yaml`. It writes one
PNG per design (`intro-statement.png`, `outro-cta.png`, `caption-pill.png` and so on) to `slides/`
in the output folder, or to the folder you give with `--out`. `--variant NAME` previews a variant.

`layout: auto` picks a layout from the storyboard `name`. Different videos get different layouts,
and a re-render of the same video gets the same one. Renaming a video can change it, so set the
layout yourself when you want control. For the outro, `auto` always picks `cta` when `outro.cta` is
set.

| Intro layout | Look |
|---|---|
| `statement` | Large condensed capitals, the key words on a highlight block. |
| `product` | Text on the left, the app's first screen on a tilted card on the right. |
| `agenda` | Title on the left, the step caption titles as a numbered list on the right (the first six and "and N more" when there are more than seven). |
| `cinematic` | The live app shows through a dark scrim, with the title low on the left. |

| Outro layout | Look |
|---|---|
| `summary` | Heading with check-marked bullets. |
| `cta` | Like `summary`, plus the `outro.cta` text with an arrow. |
| `cinematic` | The same content over the live app behind a dark scrim. |

The intro also shows the step count (except in `agenda`), the `eyebrow`, and the `intro_note`.
Put `*asterisks*` around words in `title` or `outro.heading` to set them on the highlight block.
The title of a published page and its entry in the video list are shown without the asterisks.
`outro.cta` is scanned like any other on-screen text: in public mode a link in it needs its host
in `allowed_hosts`.

## The style block

`style` controls the framed look, the colour theme and caption style, zoom, subtitles and music.
`theme`, `accent`, `captions` and `subtitles` apply whether or not the video is framed. Unknown keys
inside `style` are errors.

| Key | Type | Default | What it does |
|---|---|---|---|
| `frame` | boolean | `true` in public mode, `false` in handover mode | Place the recording on a wallpaper with rounded corners and a shadow. |
| `canvas` | `[width, height]` | `[1920, 1080]` | Size of the final video when framed. Each side 320 to 3840 pixels. Use `[1080, 1080]` for a square clip. |
| `background` | string or list | `auto` | The wallpaper. See Backgrounds. |
| `padding` | number | `0.04` | Space around the window as a fraction of the shorter canvas side. At least 0, below 0.3. |
| `radius` | integer | `18` | Corner radius of the window, in pixels. |
| `corners` | string | `squircle` | `squircle` (smooth, continuous corners) or `round` (a plain rounded rectangle). |
| `border` | boolean | `false` | A thin light border around the window, in place of the faint dark outline. |
| `fill` | boolean | `false` | Scale a recording that is smaller than the free space up to fill it. Text gets slightly softer. |
| `motion` | string | `drift` | `drift` pans the wallpaper slowly behind the still window. `none` keeps it still. |
| `shadow` | boolean | `true` | Soft shadow under the window. When false, only a thin outline. |
| `chrome` | boolean | `false` | Adds a window bar with three dots above the recording. |
| `chrome_title` | string | empty | Text centred in the window bar. Shown only when `frame` and `chrome` are both on. |
| `theme` | string | `petrol` | Colours of the slides, captions, badge and ring: `petrol` (dark, teal block, orange accent), `kinetic` (light) or `navy` (dark blue with a yellow ring). |
| `accent` | string | none | A colour as `#RRGGBB`. Replaces the theme's accent and ring colour. |
| `captions` | string | `card` | Step caption style: `card` (step counter such as 01/05, title, progress line), `pill` (a round number and the title) or `lower` (a lower third on the left with an accent bar). |
| `subtitles` | boolean | `false` | Burn the narration into the picture as subtitles, for feeds that autoplay without sound. Same text and timing as `captions.vtt`. Framed videos show them on the wallpaper below the window and reserve room for them. Unframed videos show them above the caption. |
| `zoom` | see Zoom | off | Default zoom for `click`, `type` and `hover` steps. |
| `music` | string | none | `ambient`, the path of an audio file, or `off`, `false` or `none` for no music. |
| `music_db` | number | `-28` | Music level between narration lines, as RMS dBFS. Must be `-12` or lower. |
| `duck_db` | number | `8` | How many dB quieter the music plays under narration. |

With no `style` block at all, public mode is framed and handover mode is not. When `frame` is off,
the video is the size of the viewport, and `canvas`, `background`, `padding`, `radius`, `corners`,
`border`, `fill`, `motion`, `shadow` and `chrome` do nothing.

**Placement.** The recording is placed on the canvas at 1:1 when it fits inside the canvas minus
the padding, the window bar (if on) and the subtitle band (if on). It is scaled down when it does
not fit, and scaled up only with `fill: true`. The default 1440 by 900 viewport on the default
1920 by 1080 canvas fits at full size, even with `chrome` on. A larger viewport is scaled down and
its text goes softer. Subtitles take a band below the window (118 px on a 1080 px canvas, scaled
with the shorter side), which can push a full-size viewport below 1:1. Whenever the recording is
scaled down, `studio render` prints a tip with a viewport that would fit 1:1. `viewport: auto`
picks that size for you.

**Corners.** `squircle` uses the CSS `corner-shape` property. Its radius is drawn 1.8 times larger
than `radius` so the corner looks as soft as a round one.

**Motion.** With `drift`, the wallpaper is drawn 6 percent larger than the canvas on each side and
pans inside that margin, on two slow cycles of 23 s and 31 s. The window stays still. A little fine
grain over the wallpaper stops gradients from banding after video encoding.

**Backgrounds.** `background` takes one of these:

| Value | Meaning |
|---|---|
| a preset name | One of the 21 wallpapers below. |
| a category | `dark`, `blue`, `purple`, `orange`, `green` or `light`: one preset from that group. |
| `auto` | One of all 21 presets. This is the default. |
| a list of preset names | One of those presets, for example `[aurora, ocean, dusk]`. |
| a CSS colour or gradient | Any other string, for example `"#0f172a"` or `"linear-gradient(135deg, #1e293b, #0ea5e9)"`. |
| an image path | A value ending in `.png`, `.jpg`, `.jpeg` or `.webp`. It covers the canvas. The path is relative to the storyboard's folder, or absolute. |

| Category | Presets |
|---|---|
| `dark` | `aurora`, `graphite`, `midnight`, `nebula` |
| `blue` | `blueprint`, `lagoon`, `ocean`, `sky` |
| `purple` | `dusk`, `orchid`, `violet` |
| `orange` | `citrus`, `ember`, `sunset` |
| `green` | `forest`, `meadow`, `mint` |
| `light` | `cloud`, `paper`, `peach`, `slate` |

The presets are generated gradients, so there are no photographs to license. Run
`studio backgrounds` for a labelled gallery (`--out file.png` sets the file name).

For `auto`, a category and a list, the pick comes from the storyboard `name`. Videos with different
names usually get different wallpapers, and a re-render of one video always gets the same one.
Renaming a video can change it. A variant and a cut-down have names of their own, so they can get
a different wallpaper from the base video: name one preset to keep them the same. `studio validate`
prints the wallpaper a framed video will use.

Names in a list are checked: one that is not a preset is an error. A single value that is not a
preset is not checked, because it may be CSS, so a misspelt preset name gives a plain wallpaper. A
missing image file is an error when the video is framed.

**Music.** `ambient` is a quiet pad synthesised on your machine, so there is no licence question.
A file path (WAV, FLAC or OGG, relative to the storyboard's folder) is looped or cut to the length
of the video and fades out at the end. You must have the rights to any file you use, and the file
must exist: a missing file stops the render when the video is assembled. To turn music off, remove
the key or write `none`, `off` or `false`. The music plays at `music_db` between narration lines
and `duck_db` dB lower under them. The mix peak is held below -1.5 dBFS. The voice is also saved
alone as `narration.wav`.

## Zoom

Zoom magnifies part of the page, then eases back out. A step zooms when its `zoom` is set:

| Value | Meaning |
|---|---|
| `false`, `off`, `none`, `0` | No zoom. |
| `true` or `auto` | Scale 1.5. |
| a number from 1.1 to 3 | That scale. |

Any other value is an error.

`style.zoom` sets the default for `click`, `type` and `hover` steps only. A step that has its own
`zoom` key, even `zoom: false`, ignores the default. `wait_for`, `scroll`, `goto` and `pause` steps
zoom only when they set `zoom` themselves.

The zoom aims at `zoom_on`, else `target`, else `highlight`. A step with `zoom` and none of the three
is an error. For `click`, `type` and `hover` the page zooms before the cursor moves. For the other
actions it zooms after the action and any wait. If the element is large, the scale is lowered so the
element fills at most 90 percent of the window; if that leaves almost no zoom, the step does not
zoom.

A zoom stays in place into the next step if that step also zooms. It eases out at the start of a
step with no zoom, on a route change, and before the outro. How zoom is drawn, and its limits, are
in [how-it-works.md](how-it-works.md).

## cutdown

A cut-down is a shorter video made from the same storyboard, for example a 60 to 90 second clip.
It is rendered after the full video (`--no-cut` skips it, `--cut-only` renders only it) into its
own folder.

| Key | Meaning |
|---|---|
| `name` | Name of the cut-down video. Default `<name>-cut`. `studio check` and `studio publish` find the cut-down again through this name. |
| `steps` | Step ids to keep, in play order. Required, not empty, every id must exist. Captions are renumbered from 1. |
| `title`, `intro_note`, `intro_narration`, `poster` | Replace the full video's values. When absent, the full video's values are used. |
| `outro` | Mapping with `heading`, `bullets`, `narration`, `cta`. Each replaces the full video's value. |
| `overrides` | Map from step id to `narration` and/or `caption` (`title`, `sub`) for that step in the cut-down. |

Cut-downs are for public videos only. `studio validate` builds the cut-down and scans its text as it
will be rendered, including `overrides`, `title` and `outro`: dashes are errors, and in public mode
so are banned terms and contact details. That scan runs once the rest of the storyboard has no
errors, so fix those first. The gate checks the rendered cut-down again.

## variants

A variant is the same storyboard with other settings, for example a square clip for social feeds.
Each entry under `variants:` is laid over the base storyboard:

```yaml
variants:
  square:                           # studio render walkthrough.yaml --variant square
    viewport: auto                  # fills a 1080 by 1080 canvas at 1:1
    style: { canvas: [1080, 1080], padding: 0.05, background: ocean }
```

- `studio render walkthrough.yaml --variant square` renders that variant. Without `--variant` only
  the base storyboard is rendered.
- The output folder is `<name>-<variant>`, unless the variant sets its own `name`.
- A key in a variant replaces the base value. `style`, `delivery`, `intro`, `outro` and `redact`
  are the exception: when both sides are mappings they merge key by key and the variant wins.
- A variant cannot set `steps`. Use `cutdown` for fewer steps.
- The merged result goes through every validator rule. `studio validate walkthrough.yaml` checks
  the base, then each variant, and prints each variant's name, viewport and canvas. Add
  `--variant NAME` to check one.
- A variant inherits the base `cutdown` block. Its cut-down gets its own name, `<variant name>-cut`,
  so it never overwrites the base cut-down. A `cutdown` block inside a variant replaces the whole
  base block.
- `studio check` and `studio publish` find the variant again through `timeline.json`.

The app has to lay out well at the variant's size. A square window is narrower than the default
one, so check the frames of a square render.

## What the validator enforces

Every item below is an error and stops the render.

**File and identity**
- The file must be a YAML mapping.
- `mode` must be `public` or `handover`.
- `version` must be 1.
- `name` is required and must use only lowercase letters, digits and dashes (2 to 63 characters).
- `title`, `base_url` and `sources` are required. A `base_url` or a source starting with `TODO` counts as missing.
- `navigation` must be `load` or `spa`.
- `intro.layout` must be `statement`, `product`, `agenda`, `cinematic` or `auto`.
- `outro.layout` must be `summary`, `cta`, `cinematic` or `auto`, and `cta` needs `outro.cta`.
- Every `redact.patterns` entry must compile as a regular expression.

**Steps**
- `steps` must be a list with at least one step, and each step a mapping.
- `id` is required and unique.
- `action` must be one of the seven actions.
- `target` is required for `click`, `type`, `hover` and `wait_for`.
- `text` is required for `type`.
- `caption.title` and `narration` are required.
- Caption numbers must run 1 to N in order.
- `speed_up` needs a wait: the action is `wait_for`, or the step has a `wait_for` selector.
- `speed_factor` must be 1 or more.
- `zoom` must be one of the accepted values, and needs `zoom_on`, `target` or `highlight`.
- `live_write: true` needs `confirmed_by_owner: true`.

**Style**
- `style` must be a mapping with only the keys in the table above.
- `canvas` must be two whole numbers, each from 320 to 3840.
- `style.zoom` must be an accepted zoom value.
- `theme` must be `petrol`, `kinetic` or `navy`.
- `captions` must be `card`, `pill` or `lower`.
- `corners` must be `squircle` or `round`, and `motion` must be `drift` or `none`.
- `accent`, when set, must be six hex digits after a hash, such as `#FF5A1F`.
- `padding` must be from 0 up to (not including) 0.3.
- `music_db` must be -12 or lower.
- Each name in a `background` list must be a preset.
- A framed video whose `background` is an image path needs that file to exist.

**Public mode**
- `auth` must be empty unless `seeded_test_data: true`.
- `delivery.private_link` must not be set.
- No banned term, email address, phone number or web address (other than an allowed host) in any
  text that appears on screen or in the voice: title, eyebrow, intro note, intro and outro text
  (including `outro.cta`), window bar title (when shown), and each step's caption and narration.
  The text of a cut-down is scanned too.

**Handover mode**
- `auth` is required, unless `local_copy` is true with a local `base_url`.
- `delivery.public` must be false.
- `client` is required and must be a slug (lowercase letters, digits, dashes).
- A private link needs `delivery.expires`.
- A `type` step, or a `click` step whose target or text contains a risky word, needs `live_write`
  (skipped for a local copy). The risky words are listed in [modes-and-privacy.md](modes-and-privacy.md).

**Local copy**
- `local_copy: true` needs a `base_url` on `localhost` or a loopback address.

**Cut-down**
- `cutdown.steps` must be present and every id must exist.
- `cutdown` is allowed in public mode only.

**Variants**
- `--variant NAME` must name an entry under `variants:`.
- A variant must not set `steps`.

**Copy, both modes**
- No em dash or en dash in any on-screen or spoken text, including the text of a cut-down.

Sales-copy words in on-screen or spoken text produce a warning, not an error. `studio validate`
and `studio render` print warnings.
