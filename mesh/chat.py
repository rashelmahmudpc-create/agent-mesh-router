"""চ্যাটের স্মৃতি — প্রতিটা কথা `.mesh/transcript.jsonl` এ জমা থাকে।

গ্রুপ মোডে আসল "হলঘর" হলো একটা GitHub Issue;
এই ফাইলটা শুধু ওই মেশিনের নিজের কপি/লগ।
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Store:
    path: str | Path = ".mesh/transcript.jsonl"

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: dict) -> dict:
        record = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **record}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    def recent(self, limit: int = 20) -> list[dict]:
        return self.entries()[-limit:]

    def today_count(self, agent: str) -> int:
        today = datetime.now(timezone.utc).date().isoformat()
        return sum(
            1
            for e in self.entries()
            if e.get("agent") == agent and str(e.get("ts", "")).startswith(today)
        )

    def transcript_text(self, limit: int = 12) -> str:
        rows = []
        for e in self.recent(limit):
            speaker = e.get("agent") or e.get("sender") or "unknown"
            text = (e.get("text") or "").strip().replace("\n", " ")
            if text:
                rows.append(f"- {speaker}: {text[:300]}")
        return "\n".join(rows)


def default_store() -> Store:
    return Store(os.environ.get("MESH_STORE", ".mesh/transcript.jsonl"))
