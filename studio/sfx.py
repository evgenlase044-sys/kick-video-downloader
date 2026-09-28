"""Generate sfx/riser.mp3 (hotkey R) with ffmpeg if missing."""
import os
import subprocess

EXPR = ("0.55*sin(2*PI*180*(pow(10,t/1.2)-1)*1.2/log(10))*pow(t/1.2,1.6)"
        "+0.25*(random(0)*2-1)*pow(t/1.2,2.4)")


def ensure_riser(sfx_dir):
    path = os.path.join(sfx_dir, "riser.mp3")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return True
    os.makedirs(sfx_dir, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"aevalsrc='{EXPR}':s=44100:d=1.2",
           "-af", "highpass=f=120,afade=t=out:st=1.14:d=0.06,alimiter=limit=0.89",
           "-ac", "1", "-c:a", "libmp3lame", "-b:a", "192k", path]
    try:
        return subprocess.run(cmd, capture_output=True, timeout=60).returncode == 0
    except Exception:
        return False
