"""Studio API routes: moment finder + templates (audit §6, §7 step 3/4)."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from studio import moments as M
from studio import templates as T
from studio.security import safe_join


class MomentsRequest(BaseModel):
    filename: str
    top_k: int = Field(10, ge=1, le=50)
    clip_len: float = Field(28.0, ge=5.0, le=180.0)
    use_llm: bool = False
    chat_file: Optional[str] = None          # JSON / JSONL inside downloads/
    chat: Optional[List[Dict[str, Any]]] = None
    words: Optional[List[Dict[str, Any]]] = None
    weights: Optional[Dict[str, float]] = None


class PlanRequest(BaseModel):
    template: str = "hype"
    beats: List[Dict[str, Any]] = Field(default_factory=list)
    face: Optional[Dict[str, float]] = None


def probe_duration(path: str) -> float:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
                           capture_output=True, text=True, timeout=60)
        return float(json.loads(r.stdout or "{}").get("format", {}).get("duration", 0) or 0)
    except Exception:
        return 0.0


def build_router(downloads_dir: str) -> APIRouter:
    r = APIRouter()

    def _resolve(name: str) -> str:
        try:
            p = safe_join(downloads_dir, name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        if not os.path.isfile(p):
            raise HTTPException(status_code=404, detail=f"Файл {os.path.basename(name)} не найден в downloads/")
        return p

    @r.post("/api/studio/moments")
    async def moments(req: MomentsRequest):
        path = _resolve(req.filename)
        chat = list(req.chat or [])
        if req.chat_file:
            try:
                chat += M.load_chat_file(_resolve(req.chat_file))
            except (ValueError, json.JSONDecodeError) as exc:
                raise HTTPException(status_code=400, detail=f"Лог чата не прочитан: {exc}")

        def work():
            dur = probe_duration(path)
            rms = M.audio_rms_series(path)
            return dur, M.find_moments(duration=dur, rms_db=rms, chat=chat, words=req.words or [],
                                       top_k=req.top_k, clip_len=req.clip_len, use_llm=req.use_llm,
                                       weights=req.weights)
        try:
            dur, found = await asyncio.to_thread(work)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        return {"filename": os.path.basename(path), "duration": dur, "moments": found,
                "signals": {"audio": True, "chat": bool(chat), "speech": bool(req.words), "llm": req.use_llm}}

    @r.get("/api/studio/templates")
    def templates():
        return {"templates": T.list_templates()}

    @r.post("/api/studio/templates/plan")
    def plan(req: PlanRequest):
        try:
            return {"template": req.template, "fx": T.plan_effects(req.template, req.beats, req.face)}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    return r
