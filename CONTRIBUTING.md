# Contributing

Thank you for helping. Open an issue before a large change, so we can agree on the approach first.
Small fixes can go straight to a pull request.

## Set up

You need Python 3.10 or newer and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Maazsiddiqui01/demo-studio-oss
cd demo-studio-oss
uv venv --python 3.12
uv pip install -e ".[check,dev]"
```

Activate the environment (`source .venv/bin/activate`, or `.venv\Scripts\activate` on Windows).
Then check the install:

```bash
studio doctor
```

## Run the tests

```bash
pytest
```

The tests cover the storyboard validator, variants, backgrounds and `viewport: auto`, the framed
layout, the music bed, folder publishing, the ffmpeg probe and the saved-session write-back. They
need no browser, no voice model and no network. One test runs ffmpeg, which comes with the
`imageio-ffmpeg` package when none is on your PATH.

## Smoke test with a real render

```bash
studio render examples/hello/walkthrough.yaml
```

The first run downloads Chromium and the voice model. When it finishes, play
`out/hello-demo-studio/video.mp4` and open `out/hello-demo-studio/REPORT.md`. The text scan and
the file items should say PASS. The frames item stays PENDING until a person reviews the frames.
CI runs the same render on Ubuntu with `--no-speech`.

## Rules for copy

The validator checks the first two on every storyboard, so the examples and the starter must follow
them too:

- No em dashes and no en dashes in narration, captions or slides. A dash is an error.
- Plain, instructional English. Words that read as sales copy produce a warning. The list is in
  `demo_studio/textscan.py`.
- Every factual claim in narration traces to a source listed under `sources:`. The validator only
  checks that the list exists, so check the claims yourself.

Docs follow the same style: short sentences, sentence-case headings, no dashes.

## Rules for changes

- Keep the default install free of paid services, API keys and non-commercial models. The voice is
  Kokoro-82M, which is Apache-2.0.
- When behaviour changes, update the matching file in `docs/`. The code is the source of truth:
  if a doc and the code disagree, fix the doc or fix the code in the same pull request.
- Add or adjust a test for validator and layout changes.
- Use made-up data in examples and tests. Never commit sign-in sessions, `.env` files, renders
  (`out/`) or anything that belongs to a client.

## Pull requests

Keep a pull request to one change. Say what changed and how you checked it. CI runs the tests with
Python 3.10 and 3.12 and the smoke render above.
