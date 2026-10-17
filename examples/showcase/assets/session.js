// A real coding-agent session (Claude Code) that followed the README's two prompts on 2026-10-17:
// the setup prompt and the request below. Times are seconds since the session started.
window.SESSION = {
 "setup_prompt": "Set up demo-studio on this machine: https://github.com/Maazsiddiqui01/demo-studio-oss\nRead https://raw.githubusercontent.com/Maazsiddiqui01/demo-studio-oss/main/AGENTS.md and follow\nits Setup section. Install anything that is missing, run `studio doctor --download`, and tell me\nwhen it is ready.",
 "request": "Use demo-studio to make a 30 second walkthrough of my task app in ./tidy-tasks. Show today's list, adding a task called \"Book the team retro\", and planning the day. Made-up data only. Add subtitles. Give me the video file.",
 "steps": [
  {
   "t": 5,
   "title": "Read the guide",
   "detail": "AGENTS.md, fetched from GitHub"
  },
  {
   "t": 12,
   "title": "Installed demo-studio",
   "detail": "uv tool install, from the GitHub repo"
  },
  {
   "t": 24,
   "title": "Checked the machine",
   "detail": "studio doctor --download: ready"
  },
  {
   "t": 37,
   "title": "Read the app and the docs",
   "detail": "tidy-tasks/index.html, the storyboard format"
  },
  {
   "t": 83,
   "title": "Wrote the script itself",
   "detail": "walkthroughs/tidy-tasks-30s.yaml, 5 steps, subtitles on"
  },
  {
   "t": 87,
   "title": "Rendered the video",
   "detail": "studio render"
  },
  {
   "t": 148,
   "title": "Reviewed the frames",
   "detail": "contact sheets and extra stills"
  },
  {
   "t": 248,
   "title": "Held the add step longer, rendered again",
   "detail": "the new task appeared too late"
  },
  {
   "t": 652,
   "title": "Eased a zoom that cut off the sidebar",
   "detail": "zoom 1.4 to 1.2, rendered again"
  },
  {
   "t": 707,
   "title": "Reviewed the final frames",
   "detail": "captions, subtitles, rings and zoom"
  },
  {
   "t": 715,
   "title": "Signed off",
   "detail": "studio check: gate passed"
  }
 ],
 "result": {
  "video": "30 s, 1920x1080, subtitles burned in",
  "report": "the quality gate passed",
  "passed": true
 }
};
