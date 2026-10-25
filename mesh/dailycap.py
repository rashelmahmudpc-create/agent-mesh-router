"""📅 দিনের কোটা গোনা — repo-তে রাখা ছোট ফাইল, যাতে প্রতিটা রান একই হিসাব দেখে।

কেন দরকার: প্রতিটা Actions রান আলাদা checkout। `.mesh/` ফোল্ডার gitignore-এ, তাই সেখানে
গোনা হিসাব পরের রানে হারিয়ে যায়। OpenHands-এর মতো কোটা-খরচা এজেন্টকে দিনে কয়বার
ডাকবে সেটা মনে রাখতে হয় — তাই এই ফাইলটা **repo-তে commit** করা হয় (`.mesh-daily.json`)।

গঠন:
    {"date": "2026-10-25", "counts": {"openhands": 2}}
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PATH = ".mesh-daily.json"


def _path(path: str | Path | None = None) -> Path:
    return Path(path or os.environ.get("MESH_DAILY") or DEFAULT_PATH)


def _today(today: str | None = None) -> str:
    return today or datetime.now(timezone.utc).date().isoformat()


def load(path: str | Path | None = None, today: str | None = None) -> dict:
    """আজকের হিসাব পড়া; তারিখ পাল্টালে নিজে থেকেই শূন্য থেকে শুরু।"""
    today = _today(today)
    file = _path(path)
    if not file.exists():
        return {"date": today, "counts": {}}
    try:
        data = json.loads(file.read_text(encoding="utf-8") or "{}")
    except (json.JSONDecodeError, OSError):
        return {"date": today, "counts": {}}
    if not isinstance(data, dict) or data.get("date") != today:
        return {"date": today, "counts": {}}
    counts = data.get("counts")
    return {"date": today, "counts": counts if isinstance(counts, dict) else {}}


def used(name: str, path: str | Path | None = None, today: str | None = None) -> int:
    """আজ এই এজেন্টকে কতবার ডাকা হয়েছে।"""
    return int(load(path, today)["counts"].get(name, 0) or 0)


def bump(name: str, path: str | Path | None = None, today: str | None = None) -> int:
    """একবার ডাকার হিসাব যোগ করে ফাইলটা লিখে দেয়; নতুন সংখ্যা ফেরত দেয়।"""
    today = _today(today)
    file = _path(path)
    data = load(path, today)
    count = int(data["counts"].get(name, 0) or 0) + 1
    data["counts"][name] = count
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return count


def remaining(name: str, limit: int, path: str | Path | None = None, today: str | None = None) -> int:
    """আজ আর কতবার ডাকা যাবে (সীমা না থাকলে বড় সংখ্যা)।"""
    if not limit:
        return 10**6
    return max(0, int(limit) - used(name, path, today))


def summary(path: str | Path | None = None, today: str | None = None) -> str:
    """মানুষে-পড়া এক লাইন (Issue/লগে দেখানোর জন্য)।"""
    data = load(path, today)
    if not data["counts"]:
        return f"{data['date']}: আজ এখনো কিছু ডাকা হয়নি"
    rows = ", ".join(f"{k}={v}" for k, v in sorted(data["counts"].items()))
    return f"{data['date']}: {rows}"
