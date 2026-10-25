"""ব্রেইন (AGENTS.md) ও এজেন্ট-পয়েন্টার ফাইল ঠিকঠাক আছে কি না।"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BRAIN = ROOT / "AGENTS.md"
POINTERS = ["CLAUDE.md", "GEMINI.md", ".clinerules", ".github/copilot-instructions.md"]


class BrainTest(unittest.TestCase):
    def test_brain_exists_and_is_substantial(self):
        self.assertTrue(BRAIN.exists(), "AGENTS.md নেই")
        text = BRAIN.read_text(encoding="utf-8")
        self.assertGreater(len(text), 3000)
        for heading in ("ZAYAN GLOBAL BRAIN", "RASHEL ZAYAN", "PRIORITIES", "AdmissionSky"):
            self.assertIn(heading, text)

    def test_every_agent_pointer_points_to_brain(self):
        for name in POINTERS:
            path = ROOT / name
            self.assertTrue(path.exists(), f"{name} নেই")
            self.assertIn("AGENTS.md", path.read_text(encoding="utf-8"), f"{name} ব্রেইনের দিকে দেখায় না")

    def test_no_secret_looking_strings_in_brain(self):
        text = BRAIN.read_text(encoding="utf-8")
        for marker in ("sk-or-", "sk-ant-", "AIza", "ghp_"):
            self.assertNotIn(marker, text)


if __name__ == "__main__":
    unittest.main()
