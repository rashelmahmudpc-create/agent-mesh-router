"""🔑 Key যাচাই — কোন key সত্যিই কাজ করছে, কোনটা নয়।

নিয়ম:
  • key-এর মান কখনো ছাপা হয় না (শুধু নাম + আছে/নেই + কাজ করছে কি না)
  • প্রতিটা provider-এ হালকা একটা request — কোনো টোকেন/ক্রেডিট খরচ হয় না
  • যাদের যাচাই করার নিরাপদ endpoint নেই, তাদের সৎভাবে "হাতে দেখতে হবে" বলা হয়

    python3 -m mesh.cli --check-keys
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass

OK, BAD, WARN, MANUAL = "ok", "bad", "warn", "manual"
ICON = {OK: "✅", BAD: "❌", WARN: "⚠️", MANUAL: "🖐️"}


@dataclass
class KeyResult:
    name: str
    status: str
    detail: str


# (env var, যাচাইয়ের ধরন, URL)
PROBES: dict[str, tuple[str, str]] = {
    # bearer → Authorization: Bearer <key>
    "OPENROUTER_API_KEY": ("bearer", "https://openrouter.ai/api/v1/key"),
    "GROQ_API_KEY": ("bearer", "https://api.groq.com/openai/v1/models"),
    "VERCEL_AI_GATEWAY": ("bearer", "https://ai-gateway.vercel.sh/v1/models"),
    # gemini → URL এ ?key=
    "GEMINI_API_KEY": ("gemini", "https://generativelanguage.googleapis.com/v1beta/models"),
    "GOOGLE_API_KEY": ("gemini", "https://generativelanguage.googleapis.com/v1beta/models"),
}

# যাদের নিরাপদ, খরচহীন endpoint নেই — জোর করে বলা যাবে না
MANUAL_ONLY = {
    "OPENHANDS_API_KEY": "SDK দিয়ে conversation খুলে দেখতে হয় (কোটা খরচ) — `--openhands \"হাই\"` দিয়ে যাচাই করুন",
    "CLINE_API_KEY": "Cline এর পাবলিক প্রোব endpoint নেই — এজেন্ট চালিয়ে দেখতে হবে",
}

# এই রিপোতে mesh-এর সাথে সম্পর্ক নেই (অন্য প্রজেক্টের key)
OUT_OF_SCOPE = (
    "CARTESIA_API_KEY",
    "CERTESIA_VOICE",
    "COMPOSIO_API_KEY",
    "ADMISSIONSKY_",
    "XAI_API_KEY",
)


def _request(url: str, headers: dict[str, str], timeout: int = 25) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            body = resp.read(4000).decode("utf-8", "replace")
            return resp.status, body
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception as exc:  # নেটওয়ার্ক বন্ধ / DNS
        return 0, f"{type(exc).__name__}: {exc}"


def _summarize(kind: str, body: str) -> str:
    """সফল উত্তরের ছোট সারাংশ — key নয়, শুধু দরকারি তথ্য।"""
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return ""
    if kind == "bearer" and isinstance(data, dict):
        # OpenRouter: {"data": {"label": ..., "usage": ..., "limit": ...}}
        inner = data.get("data") if isinstance(data.get("data"), dict) else data
        models = inner.get("models") if isinstance(inner, dict) else None
        parts = []
        if isinstance(inner, dict):
            if inner.get("label"):
                parts.append(f"label={inner['label']}")
            if inner.get("usage") is not None:
                parts.append(f"used={inner['usage']}")
            if inner.get("limit") is not None:
                parts.append(f"limit={inner['limit']}")
            if inner.get("is_free_tier") is not None:
                parts.append(f"free_tier={inner['is_free_tier']}")
        if isinstance(data.get("data"), list):
            parts.append(f"models={len(data['data'])}")
        if models:
            parts.append(f"models={len(models)}")
        return ", ".join(parts)
    if kind == "gemini" and isinstance(data, dict) and isinstance(data.get("models"), list):
        return f"models={len(data['models'])}"
    return ""


def check_key(name: str, value: str, opener=_request) -> KeyResult:
    if not value:
        return KeyResult(name, BAD, "খালি / পাওয়া যায়নি")
    probe = PROBES.get(name)
    if probe is None:
        if name in MANUAL_ONLY:
            return KeyResult(name, MANUAL, MANUAL_ONLY[name])
        if name.startswith(OUT_OF_SCOPE) or any(name.startswith(p) for p in OUT_OF_SCOPE):
            return KeyResult(name, WARN, "এই রিপোর এজেন্টের সাথে সম্পর্ক নেই (অন্য প্রজেক্ট)")
        return KeyResult(name, MANUAL, "যাচাইয়ের নিয়ম নেই — হাতে দেখতে হবে")

    kind, url = probe
    if kind == "gemini":
        status, body = opener(f"{url}?key={value}", {})
    else:
        status, body = opener(url, {"Authorization": f"Bearer {value}"})

    if status == 200:
        extra = _summarize(kind, body)
        return KeyResult(name, OK, "কাজ করছে" + (f" ({extra})" if extra else ""))
    if status in (401, 403):
        return KeyResult(name, BAD, f"key গ্রহণ করা হয়নি (HTTP {status}) — মেয়াদ শেষ বা ভুল")
    if status == 429:
        return KeyResult(name, WARN, "key ঠিক আছে, কিন্তু কোটা/রেট লিমিটে আটকে আছে (429)")
    if status == 0:
        return KeyResult(name, MANUAL, f"নেটওয়ার্ক সমস্যা: {body[:60]}")
    return KeyResult(name, WARN, f"অপ্রত্যাশিত উত্তর (HTTP {status})")


def check_all(environ: dict[str, str], opener=_request) -> list[KeyResult]:
    """সম্ভাব্য সব key — যেগুলো env এ আছে সেগুলো যাচাই, না থাকলে ❌ নেই।"""
    results: list[KeyResult] = []
    seen_bases: set[str] = set()

    for name in list(PROBES) + list(MANUAL_ONLY):
        base = name
        if base in seen_bases:
            continue
        seen_bases.add(base)
        value = (environ.get(base) or "").strip()
        results.append(check_key(base, value, opener=opener))
        # ঘোরানো key: NAME_2, NAME_3 …
        slot = 2
        while slot <= 5:
            var = f"{base}_{slot}"
            value = (environ.get(var) or "").strip()
            if not value:
                break
            results.append(check_key(var, value, opener=opener))
            slot += 1

    return results


def to_text(results: list[KeyResult]) -> str:
    """Issue/console এ বসানোর মতো টেবিল।"""
    lines = ["| key | ফল | বিস্তারিত |", "|---|---|---|"]
    for r in results:
        lines.append(f"| `{r.name}` | {ICON.get(r.status, '•')} | {r.detail} |")
    return "\n".join(lines)


def to_json(results: list[KeyResult]) -> str:
    return json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2)
