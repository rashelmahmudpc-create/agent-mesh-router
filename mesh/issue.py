"""🏛️ হলঘর — একটা GitHub Issue যেটাকে গ্রুপ চ্যাট বানানো হয়।

- আগের comment পড়া       → fetch_hall()
- নতুন উত্তর লেখা        → post_comment()
- key/টোকেন লুকানো        → redact() (brain §11: লগে গোপন তথ্য নয়)
"""

from __future__ import annotations

import json
import os
import re

from .textutil import HTML_COMMENT_RE, MESH_CALL_RE, clip

MARKER = "<!-- mesh:{agent} -->"

# ❌ ব্যর্থ উত্তরের চিহ্ন — পটভূমির তালিকায় এগুলো দরকার নেই (শুধু বিভ্রান্তি বাড়ায়)
FAILURE_MARKERS = ("সাড়া দিতে পারিনি", "কোনো উত্তর দিল না", "❌")

SECRET_PATTERNS = [
    re.compile(r"sk-or-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"AIza[A-Za-z0-9_\-]{20,}"),
    re.compile(r"xai-[A-Za-z0-9]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{16,}"),
]


def redact(text: str) -> str:
    """লেখা থেকে key/টোকেন মুছে ফেলে।"""
    out = text or ""
    for pattern in SECRET_PATTERNS:
        out = pattern.sub("«REDACTED»", out)
    return out


def _gh_json(args: list[str], runner) -> dict | list | None:
    code, out, _err = runner(["gh", *args], dict(os.environ), ".", 60)
    if code != 0 or not out.strip():
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def _clean_comment(text: str) -> str:
    """comment থেকে মার্কার/@mesh বাদ — এজেন্টের কাছে শুধু আসল কথা যায়।"""
    out = HTML_COMMENT_RE.sub("", text or "")
    out = MESH_CALL_RE.sub("", out.strip())
    return re.sub(r"\s+", " ", out).strip()


def fetch_hall(issue: int, runner=None, limit: int = 12, chars: int = 500) -> str:
    """Issue এর শেষ কয়েকটা comment এক টেক্সটে — এজেন্টরা এটা পড়ে উত্তর দেয়।"""
    if runner is None:
        from .adapters import subprocess_runner as runner  # pragma: no cover

    data = _gh_json(["issue", "view", str(issue), "--json", "title,body,comments"], runner)
    if not isinstance(data, dict):
        return ""

    rows = []
    title = (data.get("title") or "").strip()
    if title:
        rows.append(f"- (Issue শিরোনাম) {title}")
    body = clip(_clean_comment(data.get("body") or ""), chars)
    if body:
        rows.append(f"- (বর্ণনা) {redact(body)}")

    replied = 0
    for comment in reversed(data.get("comments") or []):
        author = ((comment.get("author") or {}).get("login") or "unknown").strip()
        text = redact(clip(_clean_comment(comment.get("body") or ""), chars))
        # ❌ ব্যর্থতার লাইনগুলো পটভূমি হিসেবে কাজে লাগে না — শুধু বিভ্রান্তি বাড়ায়
        if not text or any(bad in text for bad in FAILURE_MARKERS):
            continue
        rows.append(f"- @{author}: {text}")
        replied += 1
        if replied >= limit:
            break
    return "\n".join(rows)


def post_comment(issue: int, agent: str, label: str, text: str, runner=None, dry_run: bool = False) -> bool:
    """উত্তরটা Issue এ comment হিসেবে লিখে দেয় (নিজের চিহ্ন সহ)।"""
    if runner is None:
        from .adapters import subprocess_runner as runner  # pragma: no cover

    body = f"{MARKER.format(agent=agent)}\n**{label}**\n\n{redact(text).strip()}"
    cmd = ["gh", "issue", "comment", str(issue), "--body", body]
    if dry_run:
        print(f"[dry-run] gh issue comment {issue} ← {label}")
        return True
    code, _out, _err = runner(cmd, dict(os.environ), ".", 120)
    return code == 0
