"""ASR Engine using Groq Whisper API (PLAN §7.3).

Provides FLAC extraction, chunking with overlap for size limits,
exponential backoff retries, word/segment timestamp extraction,
hallucination filtering, and disk caching.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Any, Dict, List, Optional

import requests
from fastapi import HTTPException
from pydantic import BaseModel

DEFAULT_SPEECH_PROMPT = "Разговорная речь, видеоблог, нарезка, мемы, стрим, сленг, TikTok, YouTube Shorts, Reels, субтитры. Четкая пунктуация, заглавные буквы, эмоциональная интонация."

DEFAULT_GHOST_PHRASES = [
    "Продолжение следует", "Субтитры сделал", "Субтитры читал", "Субтитры читает",
    "Спасибо за просмотр", "Редактор субтитров", "Подписывайтесь на канал",
    "Thanks for watching", "Please subscribe", "Subtitles by", "Subtitles made by",
    "Amara.org community", "Смотреть до конца",
]

# G1: Groq free tier accepts 25 MB uploads — stay under it (module-level for tests)
ASR_SIZE_LIMIT = 24 * 1024 * 1024
ASR_CHUNK_LEN = 600.0       # seconds per chunk when over the size limit
ASR_CHUNK_OVERLAP = 5.0     # seconds of overlap between chunks


def _norm_phrase(p: str) -> str:
    return "".join(ch for ch in p.lower() if ch.isalnum()).strip()


def _load_ghost_phrases(cache_dir: Optional[str] = None) -> List[str]:
    path = os.path.join(cache_dir, "ghost_phrases.json") if cache_dir else None
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, list) and data:
                    return [str(p) for p in data]
        except Exception:
            pass
    if path:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(DEFAULT_GHOST_PHRASES, fh, ensure_ascii=False, indent=2)
        except Exception:
            pass
    return list(DEFAULT_GHOST_PHRASES)


def _asr_cache_key(file_path: str, start: float, end: float, model: str,
                   language: Optional[str], prompt: Optional[str]) -> str:
    import hashlib
    st = os.stat(file_path)
    raw = "|".join([
        os.path.abspath(file_path), str(st.st_size), str(int(st.st_mtime)),
        f"{start:.3f}", f"{end:.3f}", model, language or "", prompt or "",
    ])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _asr_cache_read(key: str, cache_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not cache_dir:
        return None
    try:
        path = os.path.join(cache_dir, key + ".json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
    except Exception:
        pass
    return None


def _asr_cache_write(key: str, payload: Dict[str, Any], cache_dir: Optional[str] = None) -> None:
    if not cache_dir:
        return
    try:
        os.makedirs(cache_dir, exist_ok=True)
        path = os.path.join(cache_dir, key + ".json")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass


class TranscribeRequest(BaseModel):
    filename: str
    start_time: float = 0.0
    duration: Optional[float] = None
    language: Optional[str] = None
    prompt: Optional[str] = None
    model: str = "whisper-large-v3-turbo"


def build_segments_from_words(words: List[Dict[str, Any]], base_offset: float = 0.0) -> List[Dict[str, Any]]:
    segments = []
    if not words:
        return segments

    current_words = []
    segment_id = 0

    for w in words:
        should_split = False
        if current_words:
            pause = w["start"] - current_words[-1]["end"]
            count = len(current_words)
            dur = w["end"] - current_words[0]["start"]
            last_word = current_words[-1]["word"].strip()
            if (
                pause > 0.35
                or count >= 3
                or dur >= 1.5
                or last_word.endswith(('.', '?', '!', '...'))
            ):
                should_split = True

        if should_split and current_words:
            start = current_words[0]["start"]
            end = current_words[-1]["end"]
            seg_text = " ".join(item["word"].strip() for item in current_words)
            segments.append({
                "id": segment_id,
                "start": round(start, 3),
                "end": round(end, 3),
                "abs_start": round(start + base_offset, 3),
                "abs_end": round(end + base_offset, 3),
                "text": seg_text,
                "words": list(current_words)
            })
            segment_id += 1
            current_words = []

        current_words.append(w)

    if current_words:
        start = current_words[0]["start"]
        end = current_words[-1]["end"]
        seg_text = " ".join(item["word"].strip() for item in current_words)
        segments.append({
            "id": segment_id,
            "start": round(start, 3),
            "end": round(end, 3),
            "abs_start": round(start + base_offset, 3),
            "abs_end": round(end + base_offset, 3),
            "text": seg_text,
            "words": list(current_words)
        })

    return segments


def _extract_asr_audio(file_path: str, start: float, duration: Optional[float], out_path: str) -> None:
    """G1: lossless mono 16 kHz FLAC slice (Groq downsamples to 16 kHz mono anyway)."""
    cmd = ["ffmpeg", "-y", "-ss", str(max(0.0, start))]
    if duration and duration > 0:
        cmd.extend(["-t", str(duration)])
    cmd.extend(["-i", file_path, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "flac", out_path])
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=300)
    if res.returncode != 0 or not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        err_msg = (res.stderr or "")[-200:]
        raise HTTPException(status_code=500, detail=f"Ошибка извлечения аудиодорожки: {err_msg}")


def _groq_post(audio_path: str, *, model: str, language: Optional[str], prompt: str,
               groq_api_key: str = "", groq_api_url: str = "") -> Dict[str, Any]:
    """G1: single Groq call with retries on 429/5xx/timeouts (exp backoff, max 5)."""
    api_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
    api_url = groq_api_url or os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/audio/transcriptions")
    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "KickClipStudio/3.0"}
    attempts = 0
    last_detail = "Groq API недоступен"
    while attempts < 5:
        attempts += 1
        try:
            with open(audio_path, "rb") as f:
                files = {"file": (os.path.basename(audio_path), f, "audio/flac")}
                data: List[tuple] = [
                    ("model", model),
                    ("response_format", "verbose_json"),
                    ("timestamp_granularities[]", "word"),
                    ("timestamp_granularities[]", "segment"),
                    ("temperature", "0"),
                    ("prompt", prompt),
                ]
                if language:
                    data.append(("language", language))
                resp = requests.post(api_url, files=files, data=data, headers=headers, timeout=120)
        except requests.RequestException as exc:
            last_detail = f"Сеть/Groq недоступны: {exc}"
            if attempts >= 5:
                break
            time.sleep(min(16, 2 ** attempts))
            continue
        if resp.status_code == 200:
            return resp.json()
        # Some models reject the `segment` granularity — degrade gracefully.
        if resp.status_code in (400, 422) and "granularit" in (resp.text or "").lower():
            try:
                with open(audio_path, "rb") as f:
                    files = {"file": (os.path.basename(audio_path), f, "audio/flac")}
                    data = [d for d in data if d[0] != "timestamp_granularities[]" or d[1] == "word"]
                    resp = requests.post(api_url, files=files, data=data, headers=headers, timeout=120)
                if resp.status_code == 200:
                    return resp.json()
            except requests.RequestException:
                pass
        if resp.status_code == 400:  # permanent — no point retrying
            raise HTTPException(status_code=400, detail=f"Ошибка Groq API (400): {resp.text[:300]}")
        last_detail = f"Ошибка Groq API ({resp.status_code}): {resp.text[:300]}"
        if resp.status_code not in (429, 500, 502, 503, 504) and attempts >= 5:
            break
        retry_after = resp.headers.get("Retry-After")
        try:
            delay = float(retry_after) if retry_after else min(16, 2 ** attempts)
        except ValueError:
            delay = min(16, 2 ** attempts)
        time.sleep(max(0.0, min(delay, 30)))
    raise HTTPException(status_code=502, detail=f"Groq API: повторные попытки исчерпаны. {last_detail}")


def _groq_words_and_filter(gj: Dict[str, Any], chunk_offset: float, ghost_set: set) -> tuple:
    """Parse Groq verbose_json: word timestamps, drop hallucinated segments and ghost phrases."""
    bad_ranges: List[tuple] = []
    for seg in gj.get("segments", []) or []:
        try:
            nsp = float(seg.get("no_speech_prob", 0.0))
            alp = float(seg.get("avg_logprob", 0.0))
            if nsp > 0.6 and alp < -1.0:
                bad_ranges.append((float(seg.get("start", 0.0)), float(seg.get("end", 0.0))))
        except (TypeError, ValueError):
            continue

    def _bad(t0: float, t1: float) -> bool:
        c = (t0 + t1) / 2.0
        return any(rs - 0.05 <= c <= re + 0.05 for rs, re in bad_ranges)

    words: List[Dict[str, Any]] = []
    for w in gj.get("words", []) or []:
        word_str = str(w.get("word", "")).strip()
        if not word_str:
            continue
        s = float(w.get("start", 0.0))
        e = float(w.get("end", 0.0))
        if _bad(s, e):
            continue
        words.append({"word": word_str, "start": round(s, 3), "end": round(e, 3)})

    dropped: List[bool] = [False] * len(words)
    for i in range(len(words)):
        acc = ""
        for j in range(i, min(i + 5, len(words))):
            acc = _norm_phrase(acc + words[j]["word"])
            if acc and acc in ghost_set:
                for k in range(i, j + 1):
                    dropped[k] = True
                break
    clean = [dict(w, start=round(w["start"] + chunk_offset, 3), end=round(w["end"] + chunk_offset, 3))
             for w, d in zip(words, dropped) if not d]
    return clean, len(bad_ranges)


def transcribe_media_handler(req: TranscribeRequest, downloads_dir: str,
                             groq_api_key: str, groq_api_url: str, _studio: Any,
                             size_limit: Optional[int] = None):
    base_name = os.path.basename(req.filename)
    file_path = os.path.join(downloads_dir, base_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Медиафайл {base_name} не найден")

    effective_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
    if not effective_key:
        raise HTTPException(status_code=400, detail="GROQ_API_KEY не задан в .env или переменных окружения")

    effective_url = groq_api_url or os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/audio/transcriptions")
    start = max(0.0, float(req.start_time))
    dur = float(req.duration) if req.duration and req.duration > 0 else None
    end_hint = start + dur if dur is not None else -1.0
    prompt = req.prompt or DEFAULT_SPEECH_PROMPT
    model = req.model or "whisper-large-v3-turbo"

    asr_cache_dir = os.path.join(downloads_dir, ".cache", "asr")
    temp_id = _studio.unique_id()
    temp_audio = os.path.join(downloads_dir, f"temp_transcribe_{temp_id}.flac")
    try:
        _extract_asr_audio(file_path, start, dur, temp_audio)
        total_bytes = os.path.getsize(temp_audio)
        total_dur = dur
        if total_dur is None:
            try:
                p = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=nw=1:nk=1", temp_audio],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=30)
                total_dur = float(p.stdout.strip())
            except Exception:
                total_dur = 0.0

        cache_key = _asr_cache_key(file_path, start, end_hint if end_hint > 0 else (start + (total_dur or 0)),
                                   model, req.language, prompt)
        cached = _asr_cache_read(cache_key, asr_cache_dir)
        if cached is not None:
            cached = dict(cached)
            cached["cache"] = "hit"
            return cached

        LIMIT = size_limit if size_limit is not None else ASR_SIZE_LIMIT
        chunk_plan: List[tuple] = []
        if total_bytes > LIMIT and total_dur and total_dur > 0:
            n_chunks = max(2, int(total_bytes / (LIMIT * 0.75)) + 1)
            chunk_len = min(ASR_CHUNK_LEN, max(1.0, total_dur / n_chunks))
            overlap = min(ASR_CHUNK_OVERLAP, chunk_len / 2.0)
            pos = 0.0
            while pos < total_dur - 0.01:
                cdur = min(chunk_len, total_dur - pos)
                chunk_plan.append((pos, cdur))
                pos += max(overlap, chunk_len - overlap)
        else:
            chunk_plan.append((0.0, total_dur))

        ghost_set = {_norm_phrase(p) for p in _load_ghost_phrases(asr_cache_dir) if p.strip()}
        all_words: List[Dict[str, Any]] = []
        bad_segments_total = 0
        for (cpos, cdur) in chunk_plan:
            part_path = temp_audio if len(chunk_plan) == 1 else os.path.join(downloads_dir, f"temp_transcribe_{temp_id}_{int(cpos)}.flac")
            if len(chunk_plan) > 1:
                cmd = ["ffmpeg", "-y", "-ss", f"{cpos:.3f}", "-t", f"{cdur:.3f}", "-i", temp_audio,
                       "-c:a", "flac", part_path]
                res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
                if res.returncode != 0 or not os.path.exists(part_path) or os.path.getsize(part_path) == 0:
                    continue
            try:
                gj = _groq_post(part_path, model=model, language=req.language, prompt=prompt,
                                groq_api_key=effective_key, groq_api_url=effective_url)
                chunk_words, bad_n = _groq_words_and_filter(gj, chunk_offset=start + cpos, ghost_set=ghost_set)
                bad_segments_total += bad_n
                edge = cdur
                for w in chunk_words:
                    center = w["start"] - (start + cpos)
                    distance = min(center, edge - center)
                    w["_edge_dist"] = distance
                    w["_chunk_seq"] = len(all_words)
                all_words.extend(chunk_words)
            finally:
                if part_path != temp_audio and os.path.exists(part_path):
                    try:
                        os.remove(part_path)
                    except Exception:
                        pass

        merged: List[Dict[str, Any]] = []
        for w in sorted(all_words, key=lambda x: (x["start"], x["end"])):
            if merged and abs(merged[-1]["start"] - w["start"]) < 0.30:
                prev = merged[-1]
                same_text = prev["word"].strip().lower() == w["word"].strip().lower()
                if same_text or w["_edge_dist"] > prev["_edge_dist"] + 0.5:
                    if w["_edge_dist"] > prev["_edge_dist"]:
                        merged[-1] = w
                    continue
            merged.append(w)
        for w in merged:
            w.pop("_edge_dist", None)
            w.pop("_chunk_seq", None)
        clean_words = [
            {"word": w["word"], "start": w["start"], "end": w["end"],
             "abs_start": round(w["start"], 3), "abs_end": round(w["end"], 3)}
            for w in merged if w["end"] > w["start"]
        ]
        clean_words = _studio.enforce_min_word_duration(clean_words, 2.0 / 60.0)

        segments = build_segments_from_words(clean_words, base_offset=0.0)
        full_text = " ".join(w["word"] for w in clean_words).strip()
        payload = {
            "status": "ok",
            "text": full_text,
            "language": req.language or "auto",
            "duration": total_dur or 0.0,
            "words": clean_words,
            "segments": segments,
            "start_offset": start,
            "cache": "miss",
            "chunks": len(chunk_plan),
            "filtered_hallucinations": bad_segments_total,
        }
        _asr_cache_write(cache_key, payload, asr_cache_dir)
        return payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка транскрибации: {str(e)}")
    finally:
        if os.path.exists(temp_audio):
            try:
                os.remove(temp_audio)
            except Exception:
                pass
