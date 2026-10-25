"""🌐 এজেন্ট টিম অ্যাপ (PWA) এর পরীক্ষা — ব্রাউজার বা ইন্টারনেট ছাড়াই চলে।

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import re
import shutil
import struct
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "docs" / "app"
WORKER = ROOT / "worker"

SHELL_FILES = ["index.html", "icons/icon-180.png", "icons/icon.svg"]

# অনুমোদিত বাইরের ঠিকানা — এর বাইরে কিছু থাকলে টেস্ট ফেল করবে
ALLOWED_CDN = (
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "cdn.jsdelivr.net",
    "cdnjs.cloudflare.com",
    "your-server.com",  # সেটিংসের প্লেসহোল্ডার
)

SECRET_PATTERNS = [
    re.compile(r"sk-or-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"AIza[A-Za-z0-9_\-]{20,}"),
]


def png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "PNG নয়"
    return struct.unpack(">II", data[16:24])


class ShellTest(unittest.TestCase):
    def setUp(self):
        self.html = (APP / "index.html").read_text(encoding="utf-8")

    def test_files_exist(self):
        for name in SHELL_FILES:
            with self.subTest(file=name):
                self.assertTrue((APP / name).is_file(), f"নেই: docs/app/{name}")

    def test_single_file_app(self):
        """অ্যাপ একটাই ফাইল — আলাদা CSS/JS ছড়িয়ে নেই।"""
        self.assertEqual([p.name for p in APP.glob("*.css")], [])
        self.assertEqual([p.name for p in APP.glob("*.js")], [])
        self.assertTrue((APP / "index.html").stat().st_size > 30_000)

    def test_only_allowlisted_cdn(self):
        urls = re.findall(r"https?://[^\s\"'())]+", self.html)
        outside = [u for u in urls if not any(host in u for host in ALLOWED_CDN)]
        self.assertEqual(outside, [], f"অননুমোদিত বাইরের লিংক: {outside[:5]}")

    def test_no_secrets(self):
        targets = [APP / "index.html", WORKER / "index.js", WORKER / "wrangler.toml",
                   ROOT / "docs" / "pwa-bn.md"]
        for path in targets:
            text = path.read_text(encoding="utf-8")
            for pattern in SECRET_PATTERNS:
                with self.subTest(file=path.name):
                    self.assertIsNone(pattern.search(text), f"{path.name}-এ secret আছে!")

    def test_referenced_local_files_exist(self):
        refs = re.findall(r'(?:src|href)="(\./[^"]+)"', self.html)
        self.assertTrue(refs, "লোকাল ফাইল রেফারেন্স নেই")
        for ref in refs:
            with self.subTest(ref=ref):
                self.assertTrue((APP / ref[2:]).is_file(), f"নেই: {ref}")

    def test_apple_touch_icon_size(self):
        self.assertEqual(png_size((APP / "icons" / "icon-180.png").read_bytes()), (180, 180))


class IosMetaTest(unittest.TestCase):
    def setUp(self):
        self.html = (APP / "index.html").read_text(encoding="utf-8")

    def test_viewport_covers_notch_and_keyboard(self):
        self.assertIn("viewport-fit=cover", self.html)
        self.assertIn("interactive-widget=resizes-content", self.html)

    def test_can_be_added_to_home_screen(self):
        self.assertIn('name="apple-mobile-web-app-capable" content="yes"', self.html)
        self.assertIn('name="apple-mobile-web-app-status-bar-style"', self.html)
        self.assertIn('rel="apple-touch-icon"', self.html)

    def test_bengali_and_safe_area(self):
        self.assertIn('lang="bn"', self.html)
        self.assertIn("env(safe-area-inset-top)", self.html)
        self.assertIn("env(safe-area-inset-bottom)", self.html)
        self.assertIn("--vh", self.html)  # কীবোর্ড খুললে উচ্চতা ঠিক রাখে

    def test_markdown_is_sanitized(self):
        """এজেন্টের লেখা DOMPurify দিয়ে পরিষ্কার হয়, নইলে escape হয়ে যায়।"""
        self.assertIn("DOMPurify.sanitize", self.html)
        self.assertIn("return '<p>'+esc(t)", self.html)


class ContractTest(unittest.TestCase):
    """ফ্রন্টএন্ড আর ব্যাকএন্ড একই চুক্তিতে কথা বলে।"""

    def setUp(self):
        self.html = (APP / "index.html").read_text(encoding="utf-8")
        self.worker = (WORKER / "index.js").read_text(encoding="utf-8")

    def test_endpoints_on_both_sides(self):
        for path in ("/api/health", "/api/agents", "/api/upload", "/api/chat"):
            with self.subTest(path=path):
                self.assertIn(path, self.html, f"ফ্রন্টএন্ডে {path} নেই")
                self.assertIn(path, self.worker, f"Worker-এ {path} নেই")

    def test_event_types_match(self):
        front = self.html.replace('"', "'")
        for etype in ("status", "thinking", "tool", "tool_result", "delta",
                      "final", "typing", "agent_message", "error"):
            with self.subTest(event=etype):
                self.assertIn(f"'{etype}'", front)
                self.assertIn(f'type: "{etype}"', self.worker)

    def test_token_only_from_env(self):
        self.assertIn("env.GITHUB_TOKEN", self.worker)
        self.assertIn("env.APP_TOKEN", self.worker)
        self.assertNotIn("Bearer ghp_", self.worker)

    def test_worker_streams(self):
        self.assertIn("text/event-stream", self.worker)


@unittest.skipUnless(shutil.which("node"), "node ইনস্টল নেই")
class NodeSideTest(unittest.TestCase):
    """JS অংশ আসলে চালিয়ে দেখা হয়।"""

    def _run(self, *args: str, timeout: int = 180) -> str:
        out = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        self.assertEqual(out.returncode, 0, (out.stdout or "") + (out.stderr or ""))
        return out.stdout

    def test_worker_behaviour(self):
        out = self._run("node", "tests/js/worker_check.mjs")
        self.assertIn("Worker সব পরীক্ষায় পাস", out)

    def test_dom_smoke(self):
        # jsdom না থাকলে স্ক্রিপ্ট নিজেই বাদ দেয় (exit 0)
        out = self._run("node", "tests/js/dom_check.mjs", timeout=300)
        self.assertTrue("সব DOM পরীক্ষা পাস" in out or "jsdom নেই" in out, out)


if __name__ == "__main__":
    unittest.main()

