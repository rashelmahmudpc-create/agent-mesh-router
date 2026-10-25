"""🆓 কোন মডেল এখন সত্যিই ফ্রি — OpenRouter এর তালিকা দেখে নিজেই বেছে নেয়।

কেন দরকার: OpenRouter এর ফ্রি তালিকা প্রায়ই বদলায়। একটা হার্ডকোড করা নাম
কয়েক দিনেই পেইড হয়ে যায় (আমাদের ক্ষেত্রেই হয়েছে)। তাই প্রতিটা রানে তাজা তালিকা দেখে
এমন একটা মডেল বেছে নিই যা —
  • ইনপুট ও আউটপুট দুটোই $0
  • tool calling সাপোর্ট করে (এজেন্টের জন্য বাধ্যতামূলক)
  • কমপক্ষে ৬৪ হাজার টোকেন context
"""

from __future__ import annotations

import json
import urllib.request

MODELS_URL = "https://openrouter.ai/api/v1/models"
MIN_CONTEXT = 64_000


def _is_free(model: dict) -> bool:
    pricing = model.get("pricing") or {}
    return all(
        str(pricing.get(key, "1")).strip() in ("0", "0.0", "0.000000")
        for key in ("prompt", "completion")
    )


def _supports_tools(model: dict) -> bool:
    params = model.get("supported_parameters") or []
    return "tools" in params


def pick_free_models(models: list[dict], limit: int = 3, min_context: int = MIN_CONTEXT) -> list[str]:
    """সবচেয়ে বড় context-এর দিক থেকে সেরা কয়েকটা ফ্রি টুল-সক্ষম মডেল।"""
    candidates = [
        m
        for m in models
        if isinstance(m, dict)
        and m.get("id")
        and _is_free(m)
        and _supports_tools(m)
        and int(m.get("context_length") or 0) >= min_context
    ]
    candidates.sort(key=lambda m: int(m.get("context_length") or 0), reverse=True)
    return [m["id"] for m in candidates[:limit]]


def pick_free_model(models: list[dict], min_context: int = MIN_CONTEXT) -> str | None:
    """তালিকা থেকে সবচেয়ে বড় context-এর ফ্রি টুল-সক্ষম মডেলের id।"""
    candidates = [
        m
        for m in models
        if isinstance(m, dict)
        and m.get("id")
        and _is_free(m)
        and _supports_tools(m)
        and int(m.get("context_length") or 0) >= min_context
    ]
    if not candidates:
        return None
    best = max(candidates, key=lambda m: int(m.get("context_length") or 0))
    return best["id"]


def fetch_models(timeout: int = 30) -> list[dict]:
    """OpenRouter এর পাবলিক তালিকা (key লাগে না)। ব্যর্থ হলে খালি তালিকা।"""
    request = urllib.request.Request(MODELS_URL, headers={"User-Agent": "agent-mesh-router"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:  # নেটওয়ার্ক নেই বা বদলেছে — চুপচাপ খালি
        return []
    return payload.get("data") or []


def discover(timeout: int = 30) -> str | None:
    return pick_free_model(fetch_models(timeout=timeout))


def discover_many(limit: int = 3, timeout: int = 30) -> list[str]:
    return pick_free_models(fetch_models(timeout=timeout), limit=limit)
