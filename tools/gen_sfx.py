#!/usr/bin/env python3
"""Generate all sfx/*.mp3 procedurally (numpy synthesis) -> CC0.

Every sound in sfx/ is synthesized by this script with a fixed RNG seed, so
the whole library is reproducible, has no third-party origin and can be
released under CC0-1.0. Regenerate with:

    python tools/gen_sfx.py

Files are encoded with the system ffmpeg (mp3, 44.1 kHz mono).
"""
import os
import subprocess
import sys

import numpy as np

SR = 44100
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SFX_DIR = os.path.join(ROOT, "sfx")
SEED = 20260926


def t(dur):
    return np.arange(int(round(dur * SR))) / SR


def env_ad(n, attack, decay_pow=2.0):
    """Attack-decay envelope over n samples."""
    e = np.ones(n)
    a = max(1, int(attack * SR))
    e[:a] = np.linspace(0, 1, a)
    dec = np.linspace(0, 1, n - a) ** decay_pow if n > a else np.zeros(max(0, n - a))
    e[a:] = 1.0 - dec
    return e


def noise_band(rng, n, lo, hi):
    x = rng.standard_normal(n)
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(n, 1 / SR)
    mask = (freqs >= lo) & (freqs <= hi)
    # 1/f tilt for a more natural texture
    mask = mask * (freqs + 200) ** -0.5
    y = np.fft.irfft(spec * mask, n)
    return y / (np.max(np.abs(y)) + 1e-9)


def stereo(mono):
    return mono.astype(np.float32)


# ---------------------------------------------------------------- recipes ---
def applause(rng, dur=1.6):
    n = int(dur * SR)
    out = np.zeros(n)
    for _ in range(int(dur * 90)):  # individual claps
        start = rng.integers(0, n - 2000)
        ln = rng.integers(700, 2200)
        clap = noise_band(rng, ln, 1000, 7000) * env_ad(ln, 0.0005, 3.0) * rng.uniform(0.2, 1.0)
        out[start:start + ln] += clap
    # crowd bed
    out += 0.35 * noise_band(rng, n, 700, 5000) * np.minimum(1, np.linspace(0.3, 1.0, n)) * env_ad(n, 0.3, 1.5)
    return out * 0.9 / (np.max(np.abs(out)) + 1e-9)


def camera_click(rng, hard=False):
    dur = 0.10 if not hard else 0.13
    n = int(dur * SR)
    out = np.zeros(n)
    for i, (pos, f, g) in enumerate([(0.005, 2600, 0.9), (0.03 if hard else 0.035, 1900, 0.6)]):
        s = int(pos * SR)
        ln = n - s
        cl = noise_band(rng, ln, f - 900, f + 1600) * env_ad(ln, 0.0004, 4.0) * g
        out[s:] += cl
    if hard:
        out += 0.5 * noise_band(rng, n, 300, 900) * env_ad(n, 0.0004, 5.0)
    return out / (np.max(np.abs(out)) + 1e-9)


def _crowd(rng, dur, base, bright):
    n = int(dur * SR)
    voices = []
    for _ in range(14):
        f = rng.uniform(base, base * 1.8)
        vibr = 1 + 0.06 * np.sin(2 * np.pi * rng.uniform(4.5, 6.5) * t(dur) + rng.uniform(0, 6))
        v = np.sin(2 * np.pi * f * vibr * t(dur))
        v += 0.5 * np.sin(2 * np.pi * f * 2.1 * t(dur))
        pulses = 1 + 0.5 * np.sign(np.sin(2 * np.pi * rng.uniform(2.5, 4.0) * t(dur)))
        voices.append(v * pulses)
    crowd = np.sum(voices, axis=0) * 0.12
    hiss = noise_band(rng, n, 500, bright)
    shout = np.linspace(0.4, 1.0, n)
    out = (crowd + 1.1 * hiss) * shout * env_ad(n, 0.08, 1.2)
    return out / (np.max(np.abs(out)) + 1e-9)


def cheer_crowd(rng):
    return _crowd(rng, 2.2, 180, 4000)


def cheer_victory(rng):
    n = int(2.6 * SR)
    body = _crowd(rng, 2.6, 200, 5200)
    fanf = np.zeros(n)
    for i, f in enumerate([392, 494, 587, 784]):
        s = int(i * 0.45 * SR)
        ln = min(n - s, int(0.5 * SR))
        tone = (np.sin(2 * np.pi * f * t(ln / SR)) + 0.4 * np.sin(2 * np.pi * f * 2 * t(ln / SR)))
        fanf[s:s + ln] += tone * env_ad(ln, 0.01, 1.5) * 0.25
    out = 0.8 * body + fanf
    return out / (np.max(np.abs(out)) + 1e-9)


def coin_win(rng):
    n = int(1.1 * SR)
    out = np.zeros(n)
    for i, f in enumerate([988, 1319, 1760]):
        s = int(i * 0.12 * SR)
        ln = min(n - s, int(0.5 * SR))
        tt = t(ln / SR)
        tone = np.sin(2 * np.pi * f * tt) * np.exp(-tt * 6)
        out[s:s + ln] += tone * 0.7
    return out / (np.max(np.abs(out)) + 1e-9)


def ding_positive(rng):
    dur = 0.9
    tt = t(dur)
    out = np.sin(2 * np.pi * 880 * tt) * np.exp(-tt * 5)
    out += 0.5 * np.sin(2 * np.pi * 1760 * tt) * np.exp(-tt * 7)
    out += 0.25 * np.sin(2 * np.pi * 2640 * tt) * np.exp(-tt * 9)
    return out * env_ad(len(out), 0.002, 1.0)


def fail_buzz(rng):
    dur = 0.45
    tt = t(dur)
    sq = np.sign(np.sin(2 * np.pi * 110 * tt)) * 0.6 + np.sign(np.sin(2 * np.pi * 110.7 * tt)) * 0.4
    tremble = 0.75 + 0.25 * np.sin(2 * np.pi * 28 * tt)
    out = sq * tremble
    out = np.tanh(out * 1.6)
    return out * env_ad(len(out), 0.004, 1.0)


def hit_small(rng):
    dur = 0.25
    tt = t(dur)
    f = 220 * np.exp(-tt * 22) + 55
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 18)
    crack = noise_band(rng, len(tt), 1500, 6000) * np.exp(-tt * 60) * 0.6
    return (body + crack) * env_ad(len(tt), 0.0005, 1.0)


def impact_epic(rng):
    dur = 1.4
    tt = t(dur)
    f = 130 * np.exp(-tt * 6) + 32
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 3.2)
    body = np.tanh(body * 2.2)
    rumble = noise_band(rng, len(tt), 30, 160) * np.exp(-tt * 2.5) * 0.9
    crash = noise_band(rng, len(tt), 900, 5000) * np.exp(-tt * 14) * 0.5
    out = body + rumble + crash
    return out * env_ad(len(out), 0.001, 1.0) / (np.max(np.abs(out)) + 1e-9)


def _laugh_unit(rng, f0, dur, rate):
    tt = t(dur)
    vibr = 1 + 0.05 * np.sin(2 * np.pi * 5 * tt)
    carrier = np.sin(2 * np.pi * f0 * vibr * tt) + 0.4 * np.sin(2 * np.pi * f0 * 2 * tt)
    pulses = 0.55 + 0.45 * np.abs(np.sin(2 * np.pi * rate * tt))
    grain = 0.15 * noise_band(rng, len(tt), 500, 2500)
    return (carrier * pulses + grain) * env_ad(len(tt), 0.02, 1.1)


def laugh_big(rng):
    out = np.zeros(int(1.3 * SR))
    for i in range(6):
        f = 150 + 40 * np.sin(i)
        s = int(i * 0.16 * SR)
        ln = int(0.22 * SR)
        if s + ln >= len(out):
            break
        out[s:s + ln] += _laugh_unit(rng, f, 0.22, 4.2) * (0.9 - 0.05 * i)
    return out / (np.max(np.abs(out)) + 1e-9)


def laugh_crowd(rng):
    n = int(2.0 * SR)
    out = np.zeros(n)
    for k in range(9):
        f = rng.uniform(120, 260)
        s = int(rng.uniform(0, 0.7) * SR)
        ln = int(rng.uniform(0.5, 1.0) * SR)
        if s + ln >= n:
            continue
        out[s:s + ln] += _laugh_unit(rng, f, ln / SR, rng.uniform(3.0, 4.6)) * rng.uniform(0.3, 0.6)
    out += 0.25 * noise_band(rng, n, 400, 3000) * env_ad(n, 0.2, 1.2)
    return out / (np.max(np.abs(out)) + 1e-9)


def level_complete(rng):
    n = int(1.5 * SR)
    out = np.zeros(n)
    for i, f in enumerate([523, 659, 784, 1047]):
        s = int(i * 0.14 * SR)
        ln = min(n - s, int(0.6 * SR))
        tt = t(ln / SR)
        tone = (np.sin(2 * np.pi * f * tt) + 0.35 * np.sign(np.sin(2 * np.pi * f * tt)) * 0.5) * np.exp(-tt * 3.5)
        out[s:s + ln] += tone * 0.55
    return out * env_ad(n, 0.005, 1.0) / (np.max(np.abs(out)) + 1e-9)


def pop_game(rng):
    dur = 0.12
    tt = t(dur)
    f = 900 * np.exp(-tt * 40) + 240
    out = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_ad(len(tt), 0.001, 2.0)
    return np.tanh(out * 1.8)


def pop_light(rng):
    dur = 0.09
    tt = t(dur)
    f = 650 * np.exp(-tt * 45) + 300
    out = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_ad(len(tt), 0.001, 2.0)
    return out * 0.8


def whoosh(rng, dur, lo, hi, attack, sweep=True):
    n = int(dur * SR)
    body = noise_band(rng, n, lo, hi)
    if sweep:  # move the spectral centroid up->down via crossfade of two bands
        a = noise_band(rng, n, hi * 0.6, hi)
        b = noise_band(rng, n, lo, lo * 1.6)
        mix = np.linspace(1, 0, n) ** 1.5
        body = a * mix + b * (1 - mix)
    shape = env_ad(n, attack, 1.6)
    return body * shape


def whoosh_cinematic(rng):
    return whoosh(rng, 1.1, 250, 3500, 0.5)


def whoosh_fast(rng):
    out = whoosh(rng, 0.45, 500, 6000, 0.25)
    return out


def whoosh_magic(rng):
    n = int(0.9 * SR)
    base = whoosh(rng, 0.9, 700, 7000, 0.3)
    shimmer = np.zeros(n)
    for _ in range(24):
        f = rng.uniform(2000, 8000)
        s = int(rng.uniform(0, 0.6) * SR)
        ln = int(rng.uniform(0.05, 0.15) * SR)
        if s >= n:
            continue
        ln = min(ln, n - s)
        if ln <= 1:
            continue
        shimmer[s:s + ln] += np.sin(2 * np.pi * f * t(ln / SR)) * env_ad(ln, 0.005, 2.0) * 0.12
    return base + shimmer


RECIPES = {
    "applause.mp3": (applause, "noise clap bursts + crowd band"),
    "camera_click.mp3": (lambda r: camera_click(r, False), "transient clicks"),
    "camera_click_hard.mp3": (lambda r: camera_click(r, True), "transient clicks + low knock"),
    "cheer_crowd.mp3": (cheer_crowd, "voice pulse stack + shout noise"),
    "cheer_victory.mp3": (cheer_victory, "crowd + major fanfare"),
    "coin_win.mp3": (coin_win, "bright arpeggio 988/1319/1760 Hz"),
    "ding_positive.mp3": (ding_positive, "880 Hz bell + harmonics"),
    "fail_buzz.mp3": (fail_buzz, "110 Hz square tremolo, tanh"),
    "hit_small.mp3": (hit_small, "pitch-dropping sine + crack"),
    "impact_epic.mp3": (impact_epic, "130->32 Hz boom, tanh, rumble + crash"),
    "laugh_big.mp3": (laugh_big, "6 pulsed formant units"),
    "laugh_crowd.mp3": (laugh_crowd, "9 detuned laugh units + bed"),
    "level_complete.mp3": (level_complete, "C-major ascend 523..1047 Hz"),
    "pop_game.mp3": (pop_game, "900->240 Hz pitch pop"),
    "pop_light.mp3": (pop_light, "650->300 Hz soft pop"),
    "whoosh_cinematic.mp3": (whoosh_cinematic, "noise sweep 250-3500 Hz"),
    "whoosh_fast.mp3": (whoosh_fast, "noise sweep 500-6000 Hz, 0.45 s"),
    "whoosh_magic.mp3": (whoosh_magic, "sweep + 24 random shimmers"),
}


def write_mp3(path, mono):
    raw = os.path.join(SFX_DIR, "_tmp_sfx.f32")
    mono = np.clip(mono, -1, 1).astype(np.float32)
    mono.tofile(raw)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1",
             "-i", raw, "-c:a", "libmp3lame", "-b:a", "192k", path],
            check=True)
    finally:
        if os.path.exists(raw):
            os.remove(raw)


def main():
    os.makedirs(SFX_DIR, exist_ok=True)
    rng = np.random.default_rng(SEED)
    credits = [
        "# SFX Credits",
        "",
        "All files in `sfx/` are **generated procedurally** by `tools/gen_sfx.py`",
        "(numpy synthesis, encoded with FFmpeg). No third-party samples are used.",
        "",
        "| File | License | Author | Source | Recipe |",
        "|---|---|---|---|---|",
    ]
    for name, (fn, desc) in RECIPES.items():
        audio = fn(rng)
        peak = np.max(np.abs(audio)) + 1e-9
        audio = audio / peak * 0.89
        path = os.path.join(SFX_DIR, name)
        write_mp3(path, stereo(audio))
        credits.append("| `{}` | CC0-1.0 | Kick Clip Studio contributors | generated by `tools/gen_sfx.py` (seed {}) | {} |".format(name, SEED, desc))
        print("wrote", name, "%.2fs" % (len(audio) / SR))
    credits += [
        "",
        "License: [CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/) —",
        "to the extent possible under law, Kick Clip Studio contributors waive all",
        "copyright and related rights in these sound effects.",
        "",
        "Regenerate: `python tools/gen_sfx.py` (deterministic, seed {}).".format(SEED),
    ]
    with open(os.path.join(SFX_DIR, "CREDITS.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(credits) + "\n")
    print("wrote sfx/CREDITS.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
