"""🔑 Key-এর অবস্থা মনে রাখা — কোন key কখন ব্যর্থ হলো।

কেন দরকার: একটা key 429 (কোটা শেষ) খেলে বারবার সেটাই চেষ্টা করে সময় নষ্ট হয়।
তাই ব্যর্থ key কিছুক্ষণ **কুলডাউনে** রাখি, তারপর আবার চেষ্টা করি।

⚠️ নিয়ম (AGENTS.md §13): key ঘোরানো শুধু **সহনশীলতার** জন্য — কোটা ফাঁকি দেওয়ার জন্য নয়।
   ২–৩টা key কর্তৃপক্ষের সীমার ভেতরেই যথেষ্ট।
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

DEFAULT_COOLDOWN = 60 * 60  # ১ ঘণ্টা


class KeyState:
    def __init__(self, path: str | Path = ".mesh/keystate.json", now=None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._now = now or (lambda: time.time())

    # ---------- পড়া/লেখা ----------

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- কাজ ----------

    def cooldown_left(self, var: str) -> int:
        """এই key আর কত সেকেন্ড বন্ধ থাকবে (০ = এখনই ব্যবহারযোগ্য)।"""
        entry = self._load().get(var) or {}
        until = float(entry.get("until") or 0)
        return max(0, int(until - self._now()))

    def is_cooling(self, var: str) -> bool:
        return self.cooldown_left(var) > 0

    def mark_failed(self, var: str, seconds: int = DEFAULT_COOLDOWN, reason: str = "") -> None:
        data = self._load()
        data[var] = {"until": self._now() + max(0, seconds), "reason": reason[:200]}
        self._save(data)

    def mark_ok(self, var: str) -> None:
        data = self._load()
        if var in data:
            data.pop(var)
            self._save(data)

    def order(self, keys: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """কুলডাউনে থাকা key গুলো পিছনে — বাকিগুলো আগের ক্রমেই।"""
        fresh = [k for k in keys if not self.is_cooling(k[0])]
        cooling = [k for k in keys if self.is_cooling(k[0])]
        return fresh + cooling


def default_state() -> KeyState:
    return KeyState(os.environ.get("MESH_KEYSTATE", ".mesh/keystate.json"))
