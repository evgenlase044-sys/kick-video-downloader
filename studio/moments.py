"""Moment finder (audit §6): turn a multi-hour VOD into a ranked top-N of
clip candidates. A human still picks; the template does the rest.

Signals, each z-scored INSIDE one VOD (so a loud streamer is not "always hype"):
  * audio   - loudness (RMS dB, 0.5 s hops via ffmpeg astats), rolling 10 s
              windows with 2 s step + "silence -> explosion" burst term;
  * chat    - optional log [{t, user, text}]: message rate vs a rolling
              baseline, unique chatters, CAPS, emotes, "clip it"; chat lags
              the moment, so its curve is shifted back by CHAT_LAG_S;
  * speech  - optional word timings (Groq/Whisper): hype-lexicon density,
              exclamations, numbers, speech rate;
  * llm     - optional: the top candidates' transcripts are ranked by an
              LLM (hook, emotional turn, self-contained, quotable) and it
              writes a hook caption.

score = w_chat*chat + w_audio*audio + w_llm*llm + w_speech*speech  (weights
renormalised over the signals that are actually present).
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

HOP_S = 0.5
WINDOW_S = 10.0
STEP_S = 2.0
CHAT_LAG_S = 15.0
DEFAULT_WEIGHTS = {"chat": 0.30, "audio": 0.30, "llm": 0.25, "speech": 0.15}

HYPE_WORDS = {
    # ru
    "бля", "блять", "пиздец", "ахах", "хаха", "аха", "кек", "жесть", "капец", "охренеть", "офигеть",
    "нифига", "ничего себе", "что", "чего", "как", "клип", "клипай", "го", "давай", "победа", "выиграл",
    "проиграл", "мама", "ор", "ору", "лол", "ебать", "нет", "да ладно", "серьёзно", "серьезно",
    # en
    "what", "no way", "omg", "wtf", "lets go", "let's go", "clip", "clip it", "insane", "crazy", "bro",
    "holy", "dude", "win", "lol", "lmao",
}
EMOTES = {"kekw", "lul", "omegalul", "pogchamp", "pog", "poggers", "monkas", "pepelaugh", "lulw",
          "kappa", "wtf", "sadge", "copium", "w", "l", "gg", "ez", "xd", "ахаха", "кек"}


@dataclass
class Moment:
    start: float
    end: float
    peak: float
    score: float
    signals: Dict[str, float] = field(default_factory=dict)
    hook: str = ""
    reason: str = ""
    text: str = ""

    def as_dict(self):
        return {"start": round(self.start, 2), "end": round(self.end, 2), "peak": round(self.peak, 2),
                "duration": round(self.end - self.start, 2), "score": round(self.score, 4),
                "signals": {k: round(v, 3) for k, v in self.signals.items()},
                "hook": self.hook, "reason": self.reason, "text": self.text[:400]}


# ── helpers ──────────────────────────────────────────────────────────────
def zscore(values: Sequence[float]) -> List[float]:
    n = len(values)
    if n == 0:
        return []
    m = sum(values) / n
    var = sum((v - m) ** 2 for v in values) / n
    sd = math.sqrt(var)
    if sd < 1e-9:
        return [0.0] * n
    return [(v - m) / sd for v in values]


def squash(z: float) -> float:
    """z-score -> 0..1 (logistic, z=0 -> 0.5, z=2 -> ~0.88)."""
    return 1.0 / (1.0 + math.exp(-z))


def window_mean(series: Sequence[float], hop: float, win: float, step: float) -> List[float]:
    if not series:
        return []
    per_win = max(1, int(round(win / hop)))
    per_step = max(1, int(round(step / hop)))
    prefix = [0.0]
    for v in series:
        prefix.append(prefix[-1] + v)
    out = []
    for i in range(0, max(1, len(series) - per_win + 1), per_step):
        j = min(len(series), i + per_win)
        out.append((prefix[j] - prefix[i]) / max(1, j - i))
    return out


# ── audio ────────────────────────────────────────────────────────────────
_RMS_RE = re.compile(r"lavfi\.astats\.Overall\.RMS_level=(-?[0-9.]+|-inf)")


def audio_rms_series(path: str, hop: float = HOP_S, ffmpeg: str = "ffmpeg", timeout: int = 3600) -> List[float]:
    """Loudness per hop (dBFS) via ffmpeg astats; no numpy needed."""
    sr = 8000
    n = max(1, int(sr * hop))
    af = (f"aresample={sr},aformat=channel_layouts=mono,asetnsamples=n={n}:p=0,"
          "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-")
    cmd = [ffmpeg, "-hide_banner", "-nostdin", "-loglevel", "error", "-i", path, "-vn", "-af", af, "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0 and not r.stdout:
        raise RuntimeError(f"ffmpeg astats failed: {r.stderr[-300:]}")
    out = []
    for m in _RMS_RE.finditer(r.stdout):
        v = m.group(1)
        out.append(-90.0 if v == "-inf" else max(-90.0, float(v)))
    return out


def audio_signal(rms_db: Sequence[float], hop: float = HOP_S) -> List[float]:
    """Per-window audio score: loudness z + burst (quiet 5 s -> loud)."""
    if not rms_db:
        return []
    loud = window_mean(rms_db, hop, WINDOW_S, STEP_S)
    pre = window_mean(rms_db, hop, 5.0, STEP_S)
    per_step = max(1, int(round(STEP_S / hop)))
    shift = max(1, int(round(5.0 / STEP_S)))
    burst = []
    for i, v in enumerate(loud):
        # max 2s-hop loudness in this window minus the 5 s just before it
        s0 = i * per_step
        seg = rms_db[s0:s0 + int(WINDOW_S / hop)]
        peak = max(seg) if seg else v
        before = pre[i - shift] if i - shift >= 0 and i - shift < len(pre) else v
        burst.append(peak - before)
    zl, zb = zscore(loud), zscore(burst)
    return [0.6 * a + 0.4 * b for a, b in zip(zl, zb)]


# ── chat ─────────────────────────────────────────────────────────────────
def _msg_weight(text: str) -> float:
    t = (text or "").strip()
    if not t:
        return 0.0
    w = 1.0
    letters = [c for c in t if c.isalpha()]
    if len(letters) >= 4 and sum(1 for c in letters if c.isupper()) / len(letters) > 0.7:
        w += 0.5
    low = t.lower()
    toks = re.findall(r"[\w']+", low)
    if any(tok in EMOTES for tok in toks):
        w += 0.5
    if "clip" in low or "клип" in low:
        w += 1.5
    if "!!" in t or "??" in t:
        w += 0.3
    return w


def chat_signal(messages: Sequence[dict], n_windows: int, lag: float = CHAT_LAG_S) -> List[float]:
    if not messages or n_windows <= 0:
        return []
    per_win = [0.0] * n_windows
    users: List[set] = [set() for _ in range(n_windows)]
    for m in messages:
        try:
            t = float(m.get("t", m.get("time", 0))) - lag
        except (TypeError, ValueError):
            continue
        w = _msg_weight(str(m.get("text", m.get("message", ""))))
        # every window [i*STEP, i*STEP+WINDOW) that contains t
        i1 = int(t // STEP_S)
        i0 = int((t - WINDOW_S) // STEP_S) + 1
        for i in range(max(0, i0), min(n_windows, i1 + 1)):
            per_win[i] += w
            users[i].add(str(m.get("user", m.get("sender", ""))))
    # rate vs rolling baseline (60 s before), plus unique chatters
    base_n = max(1, int(60 / STEP_S))
    rel = []
    for i, v in enumerate(per_win):
        lo = max(0, i - base_n)
        base = sum(per_win[lo:i]) / max(1, i - lo) if i > lo else v
        rel.append(v / (base + 1.0))
    zr, zu, za = zscore(rel), zscore([len(u) for u in users]), zscore(per_win)
    return [0.45 * a + 0.30 * b + 0.25 * c for a, b, c in zip(zr, zu, za)]


# ── speech ───────────────────────────────────────────────────────────────
def speech_signal(words: Sequence[dict], n_windows: int) -> List[float]:
    if not words or n_windows <= 0:
        return []
    hype = [0.0] * n_windows
    rate = [0.0] * n_windows
    for w in words:
        try:
            t = float(w.get("start", w.get("s", 0)))
        except (TypeError, ValueError):
            continue
        txt = str(w.get("word", w.get("text", ""))).lower().strip(" .,…")
        val = 0.0
        if txt in HYPE_WORDS:
            val += 1.0
        if "!" in txt or "?" in txt:
            val += 0.4
        if re.search(r"\d", txt):
            val += 0.3
        i1 = int(t // STEP_S)
        i0 = int((t - WINDOW_S) // STEP_S) + 1
        for i in range(max(0, i0), min(n_windows, i1 + 1)):
            hype[i] += val
            rate[i] += 1
    zh, zr = zscore(hype), zscore(rate)
    return [0.7 * a + 0.3 * b for a, b in zip(zh, zr)]


def words_text(words: Sequence[dict], start: float, end: float) -> str:
    out = []
    for w in words or []:
        try:
            t = float(w.get("start", w.get("s", 0)))
        except (TypeError, ValueError):
            continue
        if start <= t < end:
            out.append(str(w.get("word", w.get("text", ""))).strip())
    return " ".join(x for x in out if x)


# ── combine ──────────────────────────────────────────────────────────────
def combine(signals: Dict[str, List[float]], weights: Optional[Dict[str, float]] = None) -> List[float]:
    weights = dict(weights or DEFAULT_WEIGHTS)
    present = {k: v for k, v in signals.items() if v}
    if not present:
        return []
    n = min(len(v) for v in present.values())
    tot = sum(weights.get(k, 0.0) for k in present) or 1.0
    return [sum(weights.get(k, 0.0) / tot * squash(v[i]) for k, v in present.items()) for i in range(n)]


def pick_moments(scores: Sequence[float], signals: Dict[str, List[float]], duration: float, top_k: int = 10,
                 clip_len: float = 28.0, pre_roll: float = 6.0, min_gap: float = 30.0) -> List[Moment]:
    """Greedy non-maximum suppression over window scores."""
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    taken: List[Moment] = []
    for i in order:
        if len(taken) >= top_k:
            break
        center = i * STEP_S + WINDOW_S / 2
        if any(abs(center - m.peak) < min_gap for m in taken):
            continue
        # cold open: start just before the peak, keep the reaction after it
        start = max(0.0, center - pre_roll - clip_len * 0.25)
        end = min(duration if duration > 0 else start + clip_len, start + clip_len)
        taken.append(Moment(start=start, end=end, peak=center, score=float(scores[i]),
                            signals={k: squash(v[i]) for k, v in signals.items() if v and i < len(v)}))
    return taken


# ── optional LLM re-rank (Groq OpenAI-compatible API) ───────────────────
LLM_PROMPT = (
    "Ты редактор вирусных шортсов со стримов. Для каждого фрагмента транскрипта оцени от 0 до 10: "
    "hook (цепляет ли первые 2 секунды), turn (эмоциональный поворот/реакция), standalone (понятно без "
    "контекста), quote (цитируемость). Придумай короткий хук-текст (до 6 слов, по-русски) для первого кадра. "
    "Ответь ТОЛЬКО JSON-массивом: [{\"id\":0,\"hook\":0-10,\"turn\":0-10,\"standalone\":0-10,\"quote\":0-10,"
    "\"caption\":\"...\",\"reason\":\"...\"}]"
)


def llm_rank(moments: List[Moment], api_key: Optional[str] = None, model: Optional[str] = None,
             timeout: int = 60, opener=None) -> Dict[int, dict]:
    api_key = api_key or os.environ.get("GROQ_API_KEY")
    if not api_key or not moments:
        return {}
    items = [{"id": i, "text": m.text[:900]} for i, m in enumerate(moments) if m.text]
    if not items:
        return {}
    body = {"model": model or os.environ.get("STUDIO_LLM_MODEL", "llama-3.3-70b-versatile"),
            "temperature": 0.2,
            "messages": [{"role": "system", "content": LLM_PROMPT},
                         {"role": "user", "content": json.dumps(items, ensure_ascii=False)}]}
    req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions",
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    with (opener or urllib.request.urlopen)(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    m = re.search(r"\[.*\]", content, re.S)
    arr = json.loads(m.group(0)) if m else []
    out = {}
    for it in arr:
        try:
            out[int(it["id"])] = it
        except (KeyError, TypeError, ValueError):
            continue
    return out


def find_moments(*, duration: float, rms_db: Optional[Sequence[float]] = None,
                 chat: Optional[Sequence[dict]] = None, words: Optional[Sequence[dict]] = None,
                 top_k: int = 10, clip_len: float = 28.0, use_llm: bool = False,
                 weights: Optional[Dict[str, float]] = None, llm=None) -> List[dict]:
    a = audio_signal(rms_db or [])
    n = len(a) if a else max(1, int(max(0.0, duration - WINDOW_S) // STEP_S) + 1)
    signals = {"audio": a, "chat": chat_signal(chat or [], n), "speech": speech_signal(words or [], n)}
    scores = combine(signals, weights)
    moments = pick_moments(scores, signals, duration, top_k=max(top_k * 3 if use_llm else top_k, top_k),
                           clip_len=clip_len)
    for m in moments:
        m.text = words_text(words or [], m.start, m.end)
    if use_llm:
        try:
            ranked = (llm or llm_rank)(moments)
        except Exception as exc:  # network / quota: keep the heuristic ranking
            ranked = {}
            for m in moments:
                m.reason = f"LLM недоступна: {exc}"[:160]
        if ranked:
            w = dict(weights or DEFAULT_WEIGHTS)
            for i, m in enumerate(moments):
                r = ranked.get(i)
                if not r:
                    continue
                llm_score = sum(float(r.get(k, 0)) for k in ("hook", "turn", "standalone", "quote")) / 40.0
                m.signals["llm"] = llm_score
                m.score = (1 - w["llm"]) * m.score + w["llm"] * llm_score
                m.hook = str(r.get("caption", ""))[:80]
                m.reason = str(r.get("reason", ""))[:200]
            moments.sort(key=lambda m: m.score, reverse=True)
    return [m.as_dict() for m in moments[:top_k]]


def load_chat_file(path: str) -> List[dict]:
    """JSON list, or JSON-lines, of {t|time, user|sender, text|message}."""
    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read().strip()
    if not raw:
        return []
    if raw[0] == "[":
        return json.loads(raw)
    return [json.loads(line) for line in raw.splitlines() if line.strip()]
