# The demo-studio showcase

A video about demo-studio, made with demo-studio. It shows the way most people use it: paste one
prompt into a coding agent, describe the video, and get the file back.

## What is real in it

Everything the video shows comes from one real run of that flow:

- `assets/session.js` holds the setup prompt from the README, the video request that was sent,
  and the steps of the coding-agent session that followed them, with their real elapsed times.
  The agent installed demo-studio from GitHub, looked at a small task app, wrote the script
  itself, rendered the video and reviewed the frames.
- `assets/result.webm` is a clip of the video that session made, and `assets/result.jpg` its
  poster. (Playwright's Chromium does not play H.264, so the clip is VP9.)
- The secrets scene shows the real masking: the password field and the fake API key are blurred
  by demo-studio while it records.

`index.html` is the small app the storyboard drives. Its scenes are client-side routes, so the
storyboard uses `navigation: spa`, and it scales its 1440 by 780 design to whatever viewport it is
given (`viewport: auto`). Below 1100 pixels wide it switches to the layout the square cut uses.

## Render it

```bash
studio render examples/showcase/showcase.yaml
studio render examples/showcase/showcase.yaml --variant square
```

The first gives 1920x1080, the second 1080x1080 for social feeds. Both have burned-in subtitles,
because feeds autoplay muted.

## Make your own version

Run the flow yourself: paste the setup prompt from the README into your coding agent, then ask
for a video of your own app. Copy the session's steps, the request and a clip of the result into
`assets/session.js`, `assets/result.webm` and `assets/result.jpg`, and render again.
