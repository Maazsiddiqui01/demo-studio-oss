"""An optional music bed: a quiet ambient pad synthesised here (no licence question), or a file
you have the rights to. It is ducked under the narration, which the timeline marks exactly.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

# Cmaj7, Am7, Fmaj7, G6: slow, calm, nothing that pulls focus from the voice.
CHORDS = [
    [130.81, 196.00, 246.94, 329.63],
    [110.00, 164.81, 196.00, 261.63],
    [87.31, 130.81, 164.81, 220.00],
    [98.00, 146.83, 246.94, 329.63],
]
CHORD_S = 8.0


def _reverb(x: np.ndarray, sr: int, seconds: float = 2.2, wet: float = 0.35, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    ir = rng.standard_normal(n) * np.exp(-np.linspace(0, 6.5, n))
    ir /= np.sqrt(np.sum(ir ** 2))
    size = 1 << int(np.ceil(np.log2(x.size + n)))
    y = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[: x.size]
    return (1 - wet) * x + wet * y


def ambient(seconds: float, sr: int, seed: int = 3) -> np.ndarray:
    """A soft pad, normalised to an RMS of 1.0 (the caller sets the level)."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    t = np.arange(n) / sr
    out = np.zeros(n)
    fade = int(2.0 * sr)  # crossfade between chords
    for k in range(int(np.ceil(seconds / CHORD_S)) + 1):
        a = int(max(0.0, k * CHORD_S - 1.0) * sr)
        b = min(n, int(((k + 1) * CHORD_S + 1.0) * sr))
        if a >= n:
            break
        seg_t = t[a:b]
        env = np.ones(b - a)
        ramp = min(fade, (b - a) // 2)
        env[:ramp] = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, ramp))
        env[-ramp:] = 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, ramp))
        for f in CHORDS[k % len(CHORDS)]:
            lfo = 0.75 + 0.25 * np.sin(2 * np.pi * rng.uniform(0.05, 0.12) * seg_t + rng.uniform(0, 6.28))
            voice = sum(np.sin(2 * np.pi * f * d * seg_t + rng.uniform(0, 6.28)) for d in (0.9985, 1.0, 1.0015))
            voice += 0.18 * np.sin(2 * np.pi * 2 * f * seg_t)  # a little body
            out[a:b] += env * lfo * voice
    out += 0.12 * np.sin(2 * np.pi * 523.25 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.03 * t))  # faint shimmer
    out = _reverb(out, sr)
    edge_in, edge_out = int(min(2.5, seconds / 4) * sr), int(min(3.5, seconds / 4) * sr)
    out[:edge_in] *= np.linspace(0, 1, edge_in) ** 2
    out[-edge_out:] *= np.linspace(1, 0, edge_out) ** 1.5
    rms = np.sqrt(np.mean(out ** 2)) or 1.0
    return (out / rms).astype(np.float32)


def load_file(path: Path, seconds: float, sr: int) -> np.ndarray:
    """A music file (WAV, FLAC or OGG via soundfile), looped or cut to length, RMS 1.0."""
    import soundfile as sf
    a, fsr = sf.read(path, dtype="float32", always_2d=True)
    a = a.mean(axis=1)
    if fsr != sr:
        a = np.interp(np.linspace(0, a.size - 1, int(a.size * sr / fsr)), np.arange(a.size), a).astype(np.float32)
    n = int(seconds * sr)
    a = np.tile(a, int(np.ceil(n / max(1, a.size))))[:n]
    edge = int(min(3.0, seconds / 4) * sr)
    a[-edge:] *= np.linspace(1, 0, edge)
    rms = np.sqrt(np.mean(a ** 2)) or 1.0
    return a / rms


def duck_curve(n: int, sr: int, spans: list[tuple[float, float]], duck_db: float,
               attack: float = 0.25, release: float = 0.6) -> np.ndarray:
    """Gain in dB: 0 between narration lines, -duck_db while one plays, with smooth ramps.
    Worked out at 100 Hz and interpolated, so it stays fast for long videos."""
    rate = 100
    m = int(np.ceil(n / sr * rate)) + 1
    mask = np.zeros(m)
    for a, b in spans:
        mask[max(0, int((a - attack) * rate)): min(m, int((b + release * 0.5) * rate))] = 1.0
    k = int(release * rate)
    if k > 1:
        win = np.hanning(k)
        mask = np.convolve(mask, win / win.sum(), mode="same")
    curve = np.interp(np.arange(n) / sr * rate, np.arange(m), np.clip(mask, 0, 1))
    return -duck_db * curve


def bed(spec: str, seconds: float, sr: int, spans: list[tuple[float, float]], level_db: float,
        duck_db: float = 6.0, base_dir: Path | None = None) -> np.ndarray:
    """The music track at `level_db` RMS (dBFS) between lines, `duck_db` lower under narration."""
    if spec == "ambient":
        m = ambient(seconds, sr)
    else:
        p = Path(spec)
        m = load_file(p if p.is_absolute() else (base_dir or Path.cwd()) / p, seconds, sr)
    gain_db = level_db + duck_curve(m.size, sr, spans, duck_db)
    return (m * 10 ** (gain_db / 20)).astype(np.float32)
