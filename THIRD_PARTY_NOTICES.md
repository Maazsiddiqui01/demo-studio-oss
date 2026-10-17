# Third-party notices

demo-studio is MIT licensed (see `LICENSE`). It uses the components below. This file says which are
bundled in this repository, which are downloaded when you first use them, and which are installed
as Python dependencies. The demo-studio code does not modify any of the downloaded or installed
components.

## Bundled in this repository

Four variable fonts, in `demo_studio/templates/fonts/` as WOFF2 files. The slides, captions and
subtitles embed them as data URLs under the family names `DS Inter`, `DS Archivo`, `DS Mona` and
`DS Mono`, so videos look the same on every machine. Each font is licensed under the SIL Open Font
License 1.1. The licence text sits next to the font.

| Font | Copyright | Licence file | Source |
|---|---|---|---|
| Inter | 2016 The Inter Project Authors | `OFL-inter.txt` | https://github.com/rsms/inter |
| Archivo | 2020 The Archivo Project Authors | `OFL-archivo.txt` | https://github.com/Omnibus-Type/Archivo |
| Mona Sans | 2022 The Mona Sans Project Authors | `OFL-monasans.txt` | https://github.com/github/mona-sans |
| JetBrains Mono | 2020 The JetBrains Mono Project Authors | `OFL-jetbrainsmono.txt` | https://github.com/JetBrains/JetBrainsMono |

Mona Sans has the Reserved Font Name "Mona". The page loads it under its own family name, `DS Mona`.

## Downloaded when you first use them

None of these is shipped in this repository.

| Component | Licence | Source | When |
|---|---|---|---|
| Kokoro-82M voice model, as the ONNX files `kokoro-v1.0.onnx` and `voices-v1.0.bin` | Apache-2.0 | Model: https://huggingface.co/hexgrad/Kokoro-82M. Files: https://github.com/thewh1teagle/kokoro-onnx/releases (release `model-files-v1.0`) | The first render on the CPU backend. Each file is checked against a SHA-256 in the code before it is used. |
| Kokoro-82M weights from Hugging Face | Apache-2.0 | https://huggingface.co/hexgrad/Kokoro-82M | The first render with the `gpu` extra (torch backend). |
| Chromium headless shell, and full Chromium for `studio login` | BSD-3-Clause, with third-party components under their own licences | https://www.chromium.org/ | Downloaded by `playwright install`, which demo-studio runs when the browser is missing. |
| Whisper `base.en` model, converted for faster-whisper | MIT | https://github.com/openai/whisper | The first speech check, only with the `check` extra. |

## Installed as Python dependencies

| Package | Licence | Source | Notes |
|---|---|---|---|
| kokoro-onnx | MIT | https://github.com/thewh1teagle/kokoro-onnx | Runs Kokoro-82M on the CPU. |
| Playwright for Python | Apache-2.0 | https://github.com/microsoft/playwright-python | Drives the browser. |
| imageio-ffmpeg | BSD-2-Clause | https://github.com/imageio/imageio-ffmpeg | Supplies an ffmpeg program when none is on your PATH. |
| ffmpeg | LGPL 2.1 or later, or GPL 2 or later, depending on how the build was configured | https://ffmpeg.org/legal.html | Used from your PATH, from `DEMO_STUDIO_FFMPEG`, or from the imageio-ffmpeg wheel. Run as a separate program, not modified. Check the build you use if you redistribute it. |
| NumPy | BSD-3-Clause | https://numpy.org | |
| soundfile | BSD-3-Clause | https://github.com/bastibe/python-soundfile | Loads libsndfile. |
| libsndfile | LGPL 2.1 or later | https://libsndfile.github.io/libsndfile/ | Loaded by soundfile. Most soundfile wheels include a copy. |
| PyYAML | MIT | https://github.com/yaml/pyyaml | |

Optional, from the extras:

| Package | Extra | Licence | Source |
|---|---|---|---|
| kokoro (torch backend) | `gpu` | Apache-2.0 | https://github.com/hexgrad/kokoro |
| faster-whisper | `check` | MIT | https://github.com/SYSTRAN/faster-whisper |
| bcrypt | `server` | Apache-2.0 | https://github.com/pyca/bcrypt |

## Dependencies of kokoro-onnx

pip installs these with kokoro-onnx. demo-studio does not import them itself, and none is part of
this repository. Read their licences before you redistribute an environment that contains them.

| Package | Licence | Source |
|---|---|---|
| onnxruntime | MIT | https://github.com/microsoft/onnxruntime |
| phonemizer | GPL-3.0 or later | https://github.com/bootphon/phonemizer |
| espeakng-loader, which carries eSpeak NG | GPL-3.0 or later (eSpeak NG) | https://github.com/espeak-ng/espeak-ng |

Other transitive dependencies are installed by pip with their own licences.

## Voice licence

Kokoro-82M is Apache-2.0. Do not swap in a voice model with a non-commercial licence.
