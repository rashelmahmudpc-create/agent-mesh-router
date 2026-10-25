"""ছোট ছোট টেক্সট হেল্পার — কোনো বাইরের লাইব্রেরি লাগে না।"""

from __future__ import annotations

import re

MENTION_RE = re.compile(r"@([A-Za-z0-9][A-Za-z0-9_-]*)")

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


def looks_like_quota_problem(*chunks: str) -> bool:
    """আউটপুটে রেট-লিমিট, কোটা শেষ বা লগইন সমস্যার লক্ষণ আছে কি?"""
    blob = " ".join(c for c in chunks if c).lower()
    return any(marker in blob for marker in QUOTA_MARKERS)


def strip_ansi(text: str) -> str:
    """`\\x1b[91m` / `[0m` এর মতো কোড মুছে পরিষ্কার লেখা ফেরত দেয়।"""
    return ANSI_RE.sub("", text or "")


def clip(text: str, limit: int) -> str:
    """লম্বা উত্তর কেটে ছোট করে, শেষে ... বসায়।"""
    text = (text or "").strip()
    if limit <= 0 or len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"
