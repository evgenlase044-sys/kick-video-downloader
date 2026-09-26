#!/usr/bin/env python3
"""
Sync AgentRouter models to OpenCode config.

Fetches all available models from the AgentRouter API (/v1/models)
and updates the opencode.jsonc config so every model is selectable.

Usage:
    python sync_agentrouter_models.py          # preview changes
    python sync_agentrouter_models.py --apply  # write to config
"""

import json
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "opencode" / "opencode.jsonc"

# ---------- helpers ----------

REASONING_KEYWORDS = {"thinking", "deepseek", "o1", "o3", "o4"}
VISION_KEYWORDS = {"vision"}


def _pretty_name(model_id: str) -> str:
    """Turn 'claude-opus-4-8' into 'Claude Opus 4.8'."""
    parts = model_id.replace("-", " ").split()
    result = []
    i = 0
    while i < len(parts):
        # Merge version-like tokens: "4" + "8" → "4.8"
        if parts[i].isdigit() and i + 1 < len(parts) and parts[i + 1].isdigit():
            result.append(f"{parts[i]}.{parts[i + 1]}")
            i += 2
        else:
            result.append(parts[i].capitalize())
            i += 1
    return " ".join(result)


def _guess_reasoning(model_id: str) -> bool:
    lower = model_id.lower()
    return any(kw in lower for kw in REASONING_KEYWORDS)


def _guess_vision(model_id: str) -> bool:
    lower = model_id.lower()
    return any(kw in lower for kw in VISION_KEYWORDS)


def _default_limits(model_id: str) -> dict:
    lower = model_id.lower()
    if "claude" in lower:
        return {"context": 200000, "output": 32000}
    return {"context": 128000, "output": 8192}


# ---------- strip JSONC comments ----------

def strip_jsonc_comments(text: str) -> str:
    """Remove // and /* */ comments from JSONC text."""
    # Remove single-line comments (not inside strings)
    text = re.sub(r'(?<!:)//.*', '', text)
    # Remove multi-line comments
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    # Remove trailing commas before } or ]
    text = re.sub(r',\s*([}\]])', r'\1', text)
    return text


# ---------- main ----------

def main():
    apply = "--apply" in sys.argv

    # 1. Load existing config
    if not CONFIG_PATH.exists():
        print(f"❌ Config not found at {CONFIG_PATH}")
        sys.exit(1)

    raw = CONFIG_PATH.read_text(encoding="utf-8")
    cfg = json.loads(strip_jsonc_comments(raw))

    ar_cfg = cfg.get("provider", {}).get("agentrouter")
    if ar_cfg is None:
        print("❌ No 'agentrouter' provider block in config.")
        sys.exit(1)

    base_url = ar_cfg["options"]["baseURL"].rstrip("/")
    api_key = ar_cfg["options"]["apiKey"]

    # 2. Fetch models from API
    req = urllib.request.Request(
        f"{base_url}/models",
        headers={
            "Authorization": f"Bearer {api_key}",
            "User-Agent": ar_cfg["options"].get("headers", {}).get("User-Agent", "opencode/1.0.0"),
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        print(f"❌ Failed to fetch models: {e}")
        sys.exit(1)

    api_models = data.get("data", [])
    if not api_models:
        print("⚠️  API returned no models.")
        sys.exit(1)

    # 3. Build new models dict, preserving existing overrides
    existing = ar_cfg.get("models", {})
    new_models = {}

    for m in sorted(api_models, key=lambda x: x["id"]):
        mid = m["id"]
        if mid in existing:
            # Keep user's overrides
            new_models[mid] = existing[mid]
        else:
            entry = {
                "name": _pretty_name(mid),
                "limit": _default_limits(mid),
            }
            if _guess_reasoning(mid):
                entry["reasoning"] = True
            if _guess_vision(mid):
                entry["attachment"] = True
                entry["modalities"] = {
                    "input": ["text", "image"],
                    "output": ["text"],
                }
            new_models[mid] = entry

    # 4. Report
    old_ids = set(existing.keys())
    new_ids = set(new_models.keys())
    added = new_ids - old_ids
    removed = old_ids - new_ids
    kept = old_ids & new_ids

    print(f"📡 AgentRouter API returned {len(api_models)} model(s):\n")
    for mid in sorted(new_ids):
        tag = " [NEW]" if mid in added else ""
        print(f"  • {mid} — {new_models[mid]['name']}{tag}")

    if removed:
        print(f"\n🗑️  Removed (no longer in API):")
        for mid in sorted(removed):
            print(f"  • {mid}")

    print(f"\n📊 Summary: {len(kept)} kept, {len(added)} added, {len(removed)} removed")

    if not apply:
        print("\n💡 Run with --apply to write changes to config.")
        return

    # 5. Write
    ar_cfg["models"] = new_models
    cfg["provider"]["agentrouter"] = ar_cfg

    CONFIG_PATH.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"\n✅ Config updated at {CONFIG_PATH}")


if __name__ == "__main__":
    main()
