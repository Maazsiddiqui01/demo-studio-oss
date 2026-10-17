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
