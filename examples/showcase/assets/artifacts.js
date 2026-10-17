// Real artifacts from one render of the starter project (studio init, then studio render).
// Captured by the showcase build; see examples/showcase/README.md.
window.ARTIFACTS = {
 "log": {
  "cmd": "studio render walkthrough.yaml",
  "seconds": 60.0,
  "lines": [
   [
    0.73,
    "[tidy-tasks-tour] narrate: 7 lines, voice af_heart, backend kokoro-onnx on cpu"
   ],
   [
    5.01,
    "[tidy-tasks-tour] record: http://localhost:5199 at 1440x900"
   ],
   [
    13.63,
    "  step 1 list"
   ],
   [
    17.49,
    "  step 2 type"
   ],
   [
    21.19,
    "  step 3 add"
   ],
   [
    23.91,
    "  step 4 plan"
   ],
   [
    32.06,
    "  step 5 result"
   ],
   [
    42.56,
    "[tidy-tasks-tour] assemble: 686 frames"
   ],
   [
    43.99,
    "  encoding 31.4s at 1920x1080 (framed, recording at 1440x900), 30 fps"
   ],
   [
    53.52,
    "[tidy-tasks-tour] gate"
   ],
   [
    59.88,
    "[tidy-tasks-tour] done in 59s: 31.4s video at out\\tidy-tasks-tour\\video.mp4"
   ],
   [
    59.88,
    "  frames    PENDING"
   ],
   [
    59.88,
    "  text      PASS"
   ],
   [
    59.88,
    "  audio     PASS"
   ],
   [
    59.88,
    "  file      PASS"
   ],
   [
    59.88,
    "  delivery  PENDING"
   ],
   [
    59.88,
    "  vps       PASS"
   ],
   [
    59.88,
    "    speech similarity 1.0"
   ]
  ]
 },
 "storyboard": "# A starter walkthrough. Render it with:   studio render walkthrough.yaml\n# Then point base_url at your own app and rewrite the steps. Reference: docs/storyboard-format.md\nversion: 1\nname: tidy-tasks-tour               # the output folder: out/tidy-tasks-tour/\nmode: public                        # public (made-up or seeded data) or handover (a client's real data, private)\ntitle: \"Plan a day in *Tidy Tasks*\"      # *words* go on the highlight block\neyebrow: \"DEMO STUDIO STARTER\"\nintro_note: \"A made-up demo app. The waiting time is sped up.\"\nintro:\n  narration: \"This is a short tour of a small demo app, made with demo studio.\"\n  layout: auto                      # statement | product | agenda | cinematic | auto (picked from the name)\noutro:\n  heading: \"That is the whole tour\"\n  bullets: [\"Add a task in one line\", \"Plan my day puts what is due first\"]\n  narration: \"That is it. Edit the storyboard to make a video of your own app.\"\n  layout: auto                      # summary | cta | cinematic | auto\n\nbase_url: \"http://localhost:5199\"\nserve: demo-app                     # serves this folder at base_url while recording; remove it for your own app\nnavigation: load                    # load, or spa for apps with client-side routes\nauth: null                          # a saved session from `studio login <name>` for apps behind a sign-in\nvoice: \"af_heart\"                   # any Kokoro voice, for example af_bella, am_michael, bf_emma\nviewport: [1440, 900]\nsources:                            # where every claim in the narration comes from\n  - \"demo-app/index.html (made-up demo data)\"\nbanned_terms: []                    # public mode: names and words that must never appear on screen\nstyle:\n  background: aurora                # aurora | sunset | ocean | midnight | slate | a CSS colour or gradient | an image path\n  theme: petrol                     # slides and captions: petrol (dark) | kinetic (light) | navy\n  captions: card                    # card | pill | lower\n  music: ambient                    # a quiet pad made on your machine; remove for silence\n  # subtitles: true                 # burn the narration in, for feeds that autoplay muted\n  # canvas: [1080, 1080]            # a square video; `studio slides walkthrough.yaml` previews the looks\ndelivery: { public: true, private_link: false, expires: null, local_only: false }\n\nsteps:\n  - id: list\n    route: \"/\"\n    action: wait_for\n    target: \"[data-demo=list]\"\n    caption: { n: 1, title: \"Today's list\", sub: \"Four tasks, one due today\" }\n    narration: \"Here is today's list. One task is due today.\"\n  - id: type\n    action: type\n    target: \"[data-demo=new-task]\"\n    text: \"Book the team retro\"\n    zoom: auto                      # zoom in on the field before the cursor moves there\n    caption: { n: 2, title: \"Add a task\", sub: \"Type it in one line\" }\n    narration: \"To add a task, type it in one line.\"\n  - id: add\n    action: click\n    target: \"[data-demo=add]\"\n    caption: { n: 3, title: \"Save it\", sub: \"It joins the list\" }\n    narration: \"Add puts it at the end of the list.\"\n  - id: plan\n    action: click\n    target: \"[data-demo=plan]\"\n    wait_for: \"[data-demo=plan-result]\"\n    speed_up: true                  # the wait plays four times faster, and the caption says so\n    caption: { n: 4, title: \"Plan my day\", sub: \"The list is sorted for you\" }\n    narration: \"Plan my day sorts the list. The wait is sped up, and the video says so.\"\n  - id: result\n    action: pause\n    highlight: \"[data-demo=plan-result]\"\n    zoom: 1.4\n    hold: 0.6\n    caption: { n: 5, title: \"The plan\", sub: \"What is due comes first\" }\n    narration: \"The plan starts with the invoices, because they are due today.\"\n",
 "banned": [
  "INVALID:",
  "  - public mode: banned: 'Tidy Tasks' in title"
 ],
 "gate": {
  "passed": true,
  "video_s": 31.391,
  "size_mb": 4.98,
  "cues": 10,
  "items": [
   [
    "Frames",
    true,
    "6 stills and contact sheets, reviewed and signed off"
   ],
   [
    "Text scan",
    true,
    "7 screens scanned, no hits"
   ],
   [
    "Audio",
    true,
    "peak -2.3 dB, no long silences, speech match 1.0"
   ],
   [
    "File",
    true,
    "H.264 and AAC, faststart, 31.4 s, 4.98 MB"
   ],
   [
    "Delivery",
    true,
    "video, captions, poster and embed page written"
   ]
  ]
 }
};
