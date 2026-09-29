"""Studio API routes: moment finder + templates (audit §6, §7 step 3/4)
+ live chat recording to JSONL (PR #10, feeds the moment finder)."""
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
    clip_lens: Optional[List[float]] = None  # §6 P2: dual-export e.g. [25, 50] -> grouped moments
    use_llm: bool = False
    chat_file: Optional[str] = None          # JSON / JSONL inside downloads/
    chat: Optional[List[Dict[str, Any]]] = None
    words: Optional[List[Dict[str, Any]]] = None
    motion: Optional[List[float]] = None     # §6 v2 visual signals (per-window)
    face: Optional[List[float]] = None
    scene_cuts: Optional[List[float]] = None
    weights: Optional[Dict[str, float]] = None
    feedback: Optional[Dict[str, Any]] = None  # {channel, kept: [ids]}


class PlatformPolicyRequest(BaseModel):
    platform: str = "youtube"                # youtube | tiktok | kick
    duration: Optional[float] = None
    has_music: bool = False
    reused: bool = False


class MomentsFeedbackRequest(BaseModel):
    channel: Optional[str] = None
    kept: List[int] = Field(default_factory=list)
    total: int = 0


class PlanRequest(BaseModel):
    template: str = "hype"
    beats: List[Dict[str, Any]] = Field(default_factory=list)
    face: Optional[Dict[str, float]] = None


class ChatRecordRequest(BaseModel):
    channel: str                              # slug or kick.com/<slug>
    chatroom_id: Optional[int] = None         # skip the channel API lookup


class ChatStopRequest(BaseModel):
    id: str


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
            if req.clip_lens and len(req.clip_lens) >= 2:
                grouped = {}
                for cl in req.clip_lens:
                    grouped[str(cl)] = M.find_moments(duration=dur, rms_db=rms, chat=chat, words=req.words or [],
                                                      motion=req.motion, face=req.face, scene_cuts=req.scene_cuts,
                                                      top_k=req.top_k, clip_len=float(cl), use_llm=req.use_llm,
                                                      weights=req.weights)
                return dur, grouped
            return dur, M.find_moments(duration=dur, rms_db=rms, chat=chat, words=req.words or [],
                                       motion=req.motion, face=req.face, scene_cuts=req.scene_cuts,
                                       top_k=req.top_k, clip_len=req.clip_len, use_llm=req.use_llm,
                                       weights=req.weights)
        try:
            dur, found = await asyncio.to_thread(work)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        if isinstance(found, dict):
            return {"filename": os.path.basename(path), "duration": dur, "moments_by_len": found,
                    "signals": {"audio": True, "chat": bool(chat), "speech": bool(req.words), "llm": req.use_llm, "visual": bool(req.motion or req.face)}}
        return {"filename": os.path.basename(path), "duration": dur, "moments": found,
                "signals": {"audio": True, "chat": bool(chat), "speech": bool(req.words), "llm": req.use_llm, "visual": bool(req.motion or req.face)}}

    @r.get("/api/studio/templates")
    def templates():
        return {"templates": T.list_templates()}

    @r.post("/api/studio/templates/plan")
    def plan(req: PlanRequest):
        try:
            return {"template": req.template, "fx": T.plan_effects(req.template, req.beats, req.face)}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    # ── PR #10: live chat -> downloads/chat_<slug>_<time>.jsonl ──────────
    @r.post("/api/studio/chat/record")
    def chat_record(req: ChatRecordRequest):
        import chat_recorder as CR
        try:
            slug = CR.slug_from(req.channel)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        rid, rec = CR.start_recording(slug, downloads_dir, chatroom_id=req.chatroom_id)
        return {"id": rid, "file": os.path.basename(rec.out_path), "status": rec.status()}

    @r.post("/api/studio/chat/stop")
    def chat_stop(req: ChatStopRequest):
        import chat_recorder as CR
        st = CR.stop_recording(req.id)
        if st is None:
            raise HTTPException(status_code=404, detail="Запись чата не найдена")
        return {"id": req.id, "status": st}

    @r.post("/api/studio/moments/feedback")
    def moments_feedback(req: MomentsFeedbackRequest):
        M._Learner.nudge(req.channel or "", req.kept, req.total)
        return {"ok": True}

    @r.post("/api/platform/policy")
    def platform_policy(req: PlatformPolicyRequest):
        from studio import platform_policy as PP
        res = PP.check(req.platform, duration=req.duration, has_music=req.has_music, reused=req.reused)
        return res

    @r.get("/api/studio/chat/status")
    def chat_status():
        import chat_recorder as CR
        return {"recordings": CR.recordings_status()}

    return r
