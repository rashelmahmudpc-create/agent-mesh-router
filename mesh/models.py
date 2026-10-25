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
CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
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


def model_responds(model_id: str, api_key: str, timeout: int = 25) -> bool:
    """এই মডেলটা সত্যিই উত্তর দেয় কি না — ১ টোকেনের ছোট পরীক্ষা।

    তালিকায় থাকলেও অনেক ফ্রি মডেল মরে থাকে ("Model unavailable") — তাই ব্যবহারের আগে যাচাই।
    key না থাকলে যাচাই করা যায় না, তখন সত্যি ধরে নিই।
    """
    if not api_key:
        return True
    body = json.dumps(
        {"model": model_id, "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]}
    ).encode("utf-8")
    request = urllib.request.Request(
        CHAT_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "agent-mesh-router",
            "Accept": "application/json",
            "HTTP-Referer": "https://github.com/rashelmahmudpc-create/agent-mesh-router",
            "X-Title": "agent-mesh-router",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return 200 <= getattr(response, "status", 200) < 300
    except Exception:  # 404/402/429 — এই মডেল এখন চলবে না
        return False


def discover_usable(
    limit: int = 3,
    api_key: str = "",
    tries: int = 8,
    timeout: int = 30,
    fetcher=None,
    checker=None,
) -> list[str]:
    """ফ্রি মডেলের তালিকা থেকে শুধু যেগুলো সত্যিই উত্তর দেয় সেগুলো।"""
    models = (fetcher or fetch_models)(timeout=timeout)
    candidates = pick_free_models(models, limit=tries)
    check = checker or (lambda m: model_responds(m, api_key))
    good: list[str] = []
    for model in candidates:
        if check(model):
            good.append(model)
        if len(good) >= limit:
            break
    return good
