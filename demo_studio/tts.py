"""Narration: one WAV per line with Kokoro-82M (Apache-2.0).

Backends, picked in this order unless DEMO_STUDIO_TTS is set:
  kokoro       the reference package on torch (`pip install demo-studio[gpu]`); uses the GPU
               when CUDA is available
  kokoro-onnx  the default, on the CPU. Model files (about 350 MB) are downloaded once to the
               cache (DEMO_STUDIO_KOKORO_ONNX_DIR overrides the folder) and checked by SHA-256.
Kokoro-82M is Apache-2.0. Do not swap in a voice model with a non-commercial licence.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf

from .config import cache_dir

SR = 24000
_PIPES: dict = {}   # one Kokoro pipeline per language (a: American English, b: British English)
_ONNX = None
_BACKEND = None

# English voices in Kokoro v1.0 (voices-v1.0.bin). a = American, b = British; f = female, m = male.
ENGLISH_VOICES = {
    "af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore", "af_nicole", "af_nova", "af_river",
    "af_sarah", "af_sky", "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael", "am_onyx",
    "am_puck", "am_santa", "bf_alice", "bf_emma", "bf_isabella", "bf_lily", "bm_daniel", "bm_fable", "bm_george",
    "bm_lewis",
}
# The clearest voices of each kind (Kokoro's own quality grades), used by voice: auto | female | male.
VOICE_POOLS = {
    "female": ["af_heart", "af_bella", "bf_emma"],
    "male": ["am_michael", "am_fenrir", "bm_george", "am_puck"],
}


def pick_voice(spec, name: str) -> str:
    """A voice id, `female`, `male`, `auto` (either), or a list of ids: the choice comes from the
    video's name, so videos differ and a re-render keeps its voice."""
    h = int(hashlib.sha1(str(name).encode()).hexdigest(), 16)
    if isinstance(spec, (list, tuple)):
        pool = [str(v) for v in spec]
    elif spec == "auto":
        pool = VOICE_POOLS["female"] + VOICE_POOLS["male"]
    elif spec in VOICE_POOLS:
        pool = VOICE_POOLS[spec]
    else:
        return str(spec or "af_heart")
    return pool[h % len(pool)] if pool else "af_heart"


ONNX_RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
ONNX_FILES = {  # name: sha256
    "kokoro-v1.0.onnx": "7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5",
    "voices-v1.0.bin": "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d",
}


def backend() -> str:
    global _BACKEND
    if _BACKEND:
        return _BACKEND
    want = os.environ.get("DEMO_STUDIO_TTS")
    if want:
        _BACKEND = want
        return want
    try:
        import kokoro  # noqa: F401
        _BACKEND = "kokoro"
    except ImportError:
        _BACKEND = "kokoro-onnx"
    return _BACKEND


def device() -> str:
    if backend() != "kokoro":
        return "cpu"
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def _kokoro(text: str, voice: str, speed: float) -> np.ndarray:
    lang = voice[0] if voice[0] in "abefhijpz" else "a"
    if lang not in _PIPES:
        from kokoro import KPipeline
        _PIPES[lang] = KPipeline(lang_code=lang, repo_id="hexgrad/Kokoro-82M", device=device())
    parts = []
    for res in _PIPES[lang](text, voice=voice, speed=speed, split_pattern=r"\n+"):
        audio = res.audio if hasattr(res, "audio") else res[2]
        if audio is None:
            continue
        parts.append(audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio))
    return np.concatenate(parts).astype(np.float32)


def onnx_dir() -> Path:
    return Path(os.environ.get("DEMO_STUDIO_KOKORO_ONNX_DIR") or cache_dir() / "models")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def ensure_onnx_models(log=print) -> Path:
    """Download the Kokoro ONNX model files once (checked by SHA-256). Returns their folder."""
    d = onnx_dir()
    for name, sha in ONNX_FILES.items():
        dest = d / name
        if dest.exists():
            continue
        d.mkdir(parents=True, exist_ok=True)
        part = dest.with_suffix(dest.suffix + ".part")
        log(f"First run: downloading the Kokoro voice model {name} (one time) to {d}")
        with urllib.request.urlopen(ONNX_RELEASE + name, timeout=60) as r, open(part, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            done, step = 0, 0
            for block in iter(lambda: r.read(1 << 20), b""):
                f.write(block)
                done += len(block)
                if total and done * 10 // total > step:
                    step = done * 10 // total
                    log(f"  {name}: {done * 100 // total}%")
        got = _sha256(part)
        if got != sha:
            part.unlink(missing_ok=True)
            raise RuntimeError(f"{name}: checksum mismatch (got {got[:12]}..., expected {sha[:12]}...); not used")
        part.replace(dest)
    return d


def _onnx(text: str, voice: str, speed: float) -> np.ndarray:
    global _ONNX
    if _ONNX is None:
        from kokoro_onnx import Kokoro
        d = ensure_onnx_models()
        _ONNX = Kokoro(str(d / "kokoro-v1.0.onnx"), str(d / "voices-v1.0.bin"))
    lang = "en-gb" if voice.startswith("b") else "en-us"
    samples, sr = _ONNX.create(text, voice=voice, speed=speed, lang=lang)
    assert sr == SR, sr
    return np.asarray(samples, dtype=np.float32)


def _trim(a: np.ndarray, thresh: float = 0.003) -> np.ndarray:
    """Cut leading and trailing near-silence, keeping 40 ms either side."""
    idx = np.flatnonzero(np.abs(a) > thresh)
    if idx.size == 0:
        return a
    pad = int(0.04 * SR)
    return a[max(0, idx[0] - pad): min(a.size, idx[-1] + pad)]


def synth(text: str, voice: str, speed: float = 1.0) -> np.ndarray:
    b = backend()
    audio = _kokoro(text, voice, speed) if b == "kokoro" else _onnx(text, voice, speed)
    return _trim(audio)


def line_wav(text: str, voice: str, speed: float, dest: Path) -> float:
    """Write the line to dest (cached by backend, voice, speed and text). Returns seconds."""
    key = hashlib.sha256(json.dumps([backend(), voice, speed, text]).encode()).hexdigest()[:20]
    cached = cache_dir() / "tts" / f"{key}.wav"

    def make() -> None:
        # Written to a temporary name, then renamed: two renders running at once never read a
        # half-written file.
        cached.parent.mkdir(parents=True, exist_ok=True)
        tmp = cached.with_name(f"{cached.stem}.{os.getpid()}.tmp.wav")
        sf.write(tmp, synth(text, voice, speed), SR, subtype="PCM_16")
        os.replace(tmp, cached)

    if not cached.exists():
        make()
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        data, sr = sf.read(cached, dtype="float32")
    except Exception:  # a damaged cache entry (an older version wrote it in place): make it again
        make()
        data, sr = sf.read(cached, dtype="float32")
    sf.write(dest, data, sr, subtype="PCM_16")
    return len(data) / sr


def narrate(sb, audio_dir: Path) -> dict[str, dict]:
    """One WAV per narration line. Returns {line_id: {path, seconds, text}}."""
    out = {}
    for lid, text in sb.narration_lines():
        p = audio_dir / f"{lid}.wav"
        voice = sb.voice_for(lid)
        secs = line_wav(text, voice, sb.speed, p)
        out[lid] = {"path": str(p), "seconds": round(secs, 3), "text": text, "voice": voice}
    return out
