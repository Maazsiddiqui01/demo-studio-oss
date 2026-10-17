# Prompts for your coding agent

You do not need to learn demo-studio. Paste these into Claude Code, Codex or another coding agent
and it does the work: it installs the tool, looks at your app, writes the script, records the
browser, checks every frame and gives you the video file.

## 1. Set it up (once)

```text
Set up demo-studio on this machine: https://github.com/Maazsiddiqui01/demo-studio-oss
Read https://raw.githubusercontent.com/Maazsiddiqui01/demo-studio-oss/main/AGENTS.md and follow
its Setup section. Install anything that is missing, run `studio doctor --download`, and tell me
when it is ready.
```

## 2. Ask for a video

Fill in the brackets. The more detail you give about what to show and who it is for, the better
the video.

```text
Use demo-studio (https://github.com/Maazsiddiqui01/demo-studio-oss, guide in AGENTS.md) to make
a walkthrough video.
App: [a URL, or "the app in this repo" and how to start it]
Show, in order: [1. ... 2. ... 3. ...]
Who will watch: [anyone (public) | one client about their own system (private)]
Data on screen: [made-up demo data | the client's real data, kept private]
Length: [about 60 seconds]
Extras: [a square version for LinkedIn | burned-in subtitles | a light or dark look]
Write the script yourself, render it, check every frame, and give me the video file.
```

## 3. Examples

**A progress update for a client (instead of recording a Loom)**

```text
Use demo-studio to make a 60 second update video for my client of what I finished this week in
the app in this repo. Read the commits since Monday, start the app, and show the three changes
they will care about, in the order they asked for them. Made-up data. Keep the narration short
and plain, and give me the file to send.
```

**A portfolio project demo**

```text
Use demo-studio to make a 75 second demo of my project at http://localhost:5173 for my portfolio.
Show the problem it solves in one line, then the two flows that show it working. Made-up data,
subtitles, a light look that matches the app, and a square version too.
```

**A quick product demo**

```text
Use demo-studio to make a 45 second product demo of http://localhost:3000 for our landing page.
Show the main screen, the one action people sign up for, and the result. No sound needed in the
first seconds, so add subtitles.
```

**A launch clip for LinkedIn**

```text
Use demo-studio to make a 60 second video of my app at http://localhost:3000 for a LinkedIn post.
Show signing up with a demo account, creating the first project, and the dashboard filling in.
Made-up data only. Burned-in subtitles, plus a square version. Light look.
```

**A client handover**

```text
Use demo-studio to make a private handover video of the CRM I built for my client at
https://crm.example.com. Show where new leads appear, how a lead is qualified, and where the
weekly report is. It is their live system, so keep every step read-only. Tell me when to sign in
with `studio login`; I will sign in myself.
```

**Onboarding for new users**

```text
Use demo-studio to make a 90 second onboarding video of the app in this repo. Start it with
`npm run dev`, then show the three things a new user does first. Keep the narration friendly and
short. Add data-demo attributes to the buttons you need if that helps.
```

**Release notes**

```text
Use demo-studio to make a short video of what changed in the latest release of the app in this
repo. Read CHANGELOG.md, pick the two biggest changes, and show each one in the app.
```

**A proposal clip**

```text
Use demo-studio to make a 75 second clip of my demo app at http://localhost:5173 for a job
proposal. Show the two features that matter most for a sales team, with subtitles. Made-up data.
```

## 4. Changing the result

Ask in plain words, and the agent edits the script and renders again:

- "Make it shorter, cut the settings step."
- "Zoom in on the filters when you use them."
- "Use a darker look and a blue background."
- "Slow down the part where the report loads, and say what it is doing."
- "Make a square version with subtitles for LinkedIn."
- "Use a male voice." or "Use a British voice."

## 5. Everything you can change

You can ask for any of these by name, or describe the effect you want:

| What | Options |
|---|---|
| Length and pace | any length; long waits sped up and labelled; holds on important screens |
| Voice | a female or male narrator, a different one per video, two narrators in one video, any Kokoro voice (`af_heart`, `bf_emma`, `am_michael`, `bm_george`...); speaking speed |
| Look | themes `petrol` (dark), `kinetic` (light), `navy`; an accent colour in your brand |
| Background | 21 wallpapers in six colour groups, a CSS gradient, your own image, or a new one per video |
| Window | padding, corner style, border, shadow, a title bar |
| Intro and closing | layouts `statement`, `product`, `agenda`, `cinematic`, `summary`, `cta`; a highlighted phrase; a link or command on the closing slide |
| Captions | `card`, `pill` or `lower`; burned-in subtitles of the narration |
| Movement | zoom on any element, a drifting background or a still one |
| Sound | a quiet music bed, your own music file, or none |
| Shape | 16:9, square, or any canvas size, from the same script |
| Privacy | public (demo data, banned names) or private handover (real data, stays on your machine) |
| Publishing | a local folder, or your own server with an optional private link that expires |

Every key is documented in [storyboard-format.md](storyboard-format.md).
