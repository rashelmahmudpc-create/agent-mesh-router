"""ছোট ছোট টেক্সট হেল্পার — কোনো বাইরের লাইব্রেরি লাগে না।"""

from __future__ import annotations

import re

MENTION_RE = re.compile(r"@([A-Za-z0-9][A-Za-z0-9_-]*)")

# অ্যাপ/Issue থেকে আসা কাঁচা লেখার আবর্জনা
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
MESH_CALL_RE = re.compile(r"^\s*@mesh\b[ \t]*", re.IGNORECASE)

# 📱 অ্যাপের comment-এ যা থাকে: `<!-- app:1792950773735 mode:agent targets:opencode,hermes -->`
APP_MARKER_RE = re.compile(r"<!--\s*app:[^>]*?mode:(agent|group)\s*-->", re.IGNORECASE)
APP_TARGETS_RE = re.compile(
    r"<!--\s*app:[^>]*?targets:([a-zA-Z0-9_,\-]+)", re.IGNORECASE
)

# টার্মিনালের রঙ/কার্সর কোড — Issue এ গেলে অদ্ভুত অক্ষর দেখায়
ANSI_RE = re.compile(r"(?:\x1b|◈)\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\[\d+m")

# এগুলো দেখলে বোঝা যায় "এই key/মডেল দিয়ে আর চলবে না" → পরের key বা fallback কমান্ড চেষ্টা করি
QUOTA_MARKERS = (
    "429",
    "rate limit",
    "rate-limit",
    "ratelimit",
    "too many requests",
    "quota",
    "insufficient_quota",
    "resource exhausted",
    "overloaded",
    "usage limit",
    "free usage limit",
    "more credits",
    "insufficient credits",
    "out of credits",
    "unauthorized",
    "not logged in",
    "no api key",
    "authentication",
    "unavailable for free",
    "model is unavailable",
    "model unavailable",
    "model not found",
    "not allowed to access model",
    "no allowed providers",
    "does not exist",
    "no endpoints found",
    "404",
)


def find_mentions(text: str, known: list[str] | None = None) -> list[str]:
    """`@opencode` এর মতো ডাকগুলো বের করে (ক্রম না বদলে, পুনরাবৃত্তি ছাড়া)।"""
    found: list[str] = []
    for raw in MENTION_RE.findall(text or ""):
        name = raw.lower()
        if known is not None and name not in known:
            continue
        if name not in found:
            found.append(name)
    return found


def app_mode_of(text: str) -> str:
    """অ্যাপের মার্কার থেকে মোড পড়ি — `agent` / `group`; অ্যাপ না হলে খালি।

    অ্যাপে দুইটা ট্যাব আছে: 👤 এজেন্ট (একজন উত্তর দেবে) আর 👥 গ্রুপ (সবাই)।
    এই মার্কারটাই Actions-কে বলে দেয় কোনটা চালাতে হবে।
    """
    match = APP_MARKER_RE.search(text or "")
    return match.group(1).lower() if match else ""


def app_targets_of(text: str) -> list[str]:
    """অ্যাপের ড্রপ-ডাউন থেকে বাছা এজেন্টদের নাম — না বাছলে খালি তালিকা।

    একজনে টিক = শুধু সে-ই উত্তর দেবে; একাধিকে টিক = যাদের টিক দিয়েছেন সবাই।
    """
    match = APP_TARGETS_RE.search(text or "")
    if not match:
        return []
    out: list[str] = []
    for raw in match.group(1).split(","):
        name = raw.strip().lower()
        if name and name not in out:
            out.append(name)
    return out


def clean_prompt(text: str) -> str:
    """অ্যাপ/Issue থেকে আসা কাঁচা লেখা পরিষ্কার করে।

    কাঁচা comment-এ `@mesh` ডাক আর `<!-- app:… -->` মার্কার থাকে — ওগুলো
    এজেন্টের কাছে গেলে সে বিভ্রান্ত হয়ে ডাকটাই ফিরিয়ে লেখে। তাই বাদ দিই।
    """
    out = HTML_COMMENT_RE.sub("", text or "")
    out = MESH_CALL_RE.sub("", out.strip())
    out = re.sub(r"[ \t]+\n", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out  # সব বাদ পড়লে (শুধুই মার্কার ছিল) খালি ফেরাই — কলার ঠিক করবে


def looks_like_quota_problem(*chunks: str) -> bool:
    """আউটপুটে রেট-লিমিট, কোটা শেষ বা লগইন সমস্যার লক্ষণ আছে কি?"""
    blob = " ".join(c for c in chunks if c).lower()
    return any(marker in blob for marker in QUOTA_MARKERS)


# কিছু ফ্রি মডেল টুল-কল লেখা হিসেবে ছাপে (Claude Code/OpenCode) — ওগুলো উত্তর নয়
TOOL_CALL_RE = re.compile(r"<tool_call>.*?</tool_call>|<tool_call>.*\Z", re.DOTALL)
TOOL_XML_RE = re.compile(r"</?(?:tool_call|param_key|param_value|function_calls?|invoke)\b[^>]*>")
TOOL_XML_TAIL_RE = re.compile(r"<tool_call>.*\Z", re.DOTALL)


def strip_tool_calls(text: str) -> str:
    """`<tool_call>…` ব্লকগুলো সরিয়ে দেয় (থাকলে উত্তর পড়া যায় না)।"""
    text = TOOL_CALL_RE.sub("", text or "")
    return TOOL_XML_TAIL_RE.sub("", text)


def strip_ansi(text: str) -> str:
    """`\\x1b[91m` / `[0m` এর মতো কোড মুছে পরিষ্কার লেখা ফেরত দেয়।"""
    return ANSI_RE.sub("", text or "")


# Hermes/অন্য টুলের অপ্রয়োজনীয় লাইন — Issue এ না আসাই ভালো
NOISE_LINES = (
    "security scanner enabled but not available",
    "command scanning will use pattern matching only",
)

REASONING_START = ("┌─ reasoning", "┌─ Reasoning".lower())


def clean_reply(text: str) -> str:
    """টার্মিনালের আবর্জনা, রিজনিং বক্স আর টুলের সতর্কবার্তা সরিয়ে পরিষ্কার উত্তর।"""
    out: list[str] = []
    in_reasoning = False
    for raw in strip_ansi(strip_tool_calls(text)).splitlines():
        low = raw.strip().lower()
        if low.startswith("┌─") and "reasoning" in low:
            in_reasoning = True
            continue
        if in_reasoning:
            if low.startswith("└"):
                in_reasoning = False
            continue
        if any(noise in low for noise in NOISE_LINES):
            continue
        out.append(raw)
    cleaned = "\n".join(out).strip()
    if cleaned:
        return cleaned
    # সব লেখা reasoning বক্সে ঢাকা পড়লে (বক্স বন্ধ না হলে) খালি উত্তর না দিয়ে
    # কাঁচা লেখাটাই ফেরত দিই — অসম্পূর্ণ উত্তরও খালি উত্তরের চেয়ে ভালো।
    salvage = [line for line in strip_ansi(strip_tool_calls(text)).splitlines()
               if line.strip() and not any(noise in line.lower() for noise in NOISE_LINES)]
    return "\n".join(salvage).strip()


def clip(text: str, limit: int) -> str:
    """লম্বা উত্তর কেটে ছোট করে, শেষে ... বসায়।"""
    text = (text or "").strip()
    if limit <= 0 or len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"
