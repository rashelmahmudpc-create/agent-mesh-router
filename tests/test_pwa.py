"""🌐 মেশ চ্যাট (PWA) এর পরীক্ষা — ব্রাউজার বা ইন্টারনেট ছাড়াই চলে।

    python3 -m unittest discover -s tests -v

যা যাচাই হয়:
  - দরকারি সব ফাইল আছে
  - manifest ঠিক আছে, আইকন সত্যিই PNG
  - iPhone-এর জন্য দরকারি meta ট্যাগ আছে
  - safe-area / 100dvh আছে (নচ ও হোম-বারে লেখা ঢাকে না)
  - কোনো বাইরের CDN নেই, কোনো secret নেই
"""

from __future__ import annotations

import json
import re
import shutil
import struct
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "docs" / "app"
WORKER = ROOT / "worker"

SHELL_FILES = [
    "index.html",
    "app.css",
    "app.js",
    "manifest.webmanifest",
    "sw.js",
    "js/md.js",
    "js/api.js",
    "js/store.js",
    "icons/icon.svg",
    "icons/icon-180.png",
    "icons/icon-192.png",
    "icons/icon-512.png",
    "icons/icon-maskable-512.png",
]

SECRET_PATTERNS = [
    re.compile(r"sk-or-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"AIza[A-Za-z0-9_\-]{20,}"),
]


def png_size(data: bytes) -> tuple[int, int]:
    """PNG এর IHDR থেকে প্রস্থ/উচ্চতা।"""
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "PNG নয়"
    width, height = struct.unpack(">II", data[16:24])
    return width, height


class ShellTest(unittest.TestCase):
    def test_all_shell_files_exist(self):
        for name in SHELL_FILES:
            with self.subTest(file=name):
                self.assertTrue((WEB / name).is_file(), f"নেই: web/{name}")

    def test_no_framework_or_cdn(self):
        """বাইরের কোনো লাইব্রেরি নেই — অ্যাপ নিজের পায়ে দাঁড়ায়।"""
        for path in list(WEB.rglob("*.html")) + list(WEB.rglob("*.css")) + list(WEB.rglob("*.js")):
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                self.assertNotIn("cdn.", text)
                self.assertNotIn("unpkg.com", text)
                self.assertNotIn("jsdelivr", text)
                self.assertNotIn("googleapis", text)

    def test_no_secrets_in_web_or_worker(self):
        targets = list(WEB.rglob("*.*")) + [WORKER / "index.js", WORKER / "wrangler.toml"]
        for path in targets:
            if path.suffix == ".png":
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in SECRET_PATTERNS:
                with self.subTest(file=path.name):
                    self.assertIsNone(pattern.search(text), f"{path.name}-এ secret আছে!")

    def test_referenced_files_exist(self):
        """HTML-এ যেসব ফাইলের কথা লেখা, সব সত্যিই আছে।"""
        html = (WEB / "index.html").read_text(encoding="utf-8")
        refs = re.findall(r'(?:src|href)="(\./[^"]+)"', html)
        self.assertTrue(refs, "index.html-এ কোনো লোকাল ফাইল রেফারেন্স নেই")
        for ref in refs:
            with self.subTest(ref=ref):
                self.assertTrue((WEB / ref[2:]).is_file(), f"নেই: {ref}")

    def test_js_imports_resolve(self):
        """JS মডিউলের সব import ঠিক জায়গায় আছে।"""
        files = [WEB / "app.js", *sorted((WEB / "js").glob("*.js"))]
        for js in files:
            text = js.read_text(encoding="utf-8")
            for imp in re.findall(r'from\s+"(\./[^"]+)"', text):
                with self.subTest(file=js.name, target=imp):
                    self.assertTrue((js.parent / imp).resolve().is_file(), f"নেই: {imp}")

    def test_service_worker_caches_every_shell_file(self):
        sw = (WEB / "sw.js").read_text(encoding="utf-8")
        for name in SHELL_FILES:
            if name == "sw.js":
                continue
            with self.subTest(file=name):
                self.assertIn(f'"./{name}"', sw)


class IosMetaTest(unittest.TestCase):
    def setUp(self):
        self.html = (WEB / "index.html").read_text(encoding="utf-8")

    def test_viewport_covers_notch(self):
        self.assertIn("viewport-fit=cover", self.html)

    def test_can_be_added_to_home_screen(self):
        self.assertIn('name="apple-mobile-web-app-capable" content="yes"', self.html)
        self.assertIn('name="apple-mobile-web-app-status-bar-style"', self.html)
        self.assertIn('rel="apple-touch-icon"', self.html)
        self.assertIn('rel="manifest"', self.html)

    def test_bengali_and_mobile_first(self):
        self.assertIn('lang="bn"', self.html)
        self.assertIn('name="viewport"', self.html)
        css = (WEB / "app.css").read_text(encoding="utf-8")
        self.assertIn("100dvh", css)
        self.assertIn("env(safe-area-inset-bottom", css)
        self.assertIn("env(safe-area-inset-top", css)

    def test_no_inline_script(self):
        """কোড শুধু app.js-এ — XSS/CSP পরিষ্কার থাকে।"""
        self.assertIsNone(re.search(r"<script(?![^>]*src=)", self.html))


class ManifestTest(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((WEB / "manifest.webmanifest").read_text(encoding="utf-8"))

    def test_required_fields(self):
        for key in ("name", "short_name", "start_url", "display", "icons", "theme_color",
                    "background_color", "lang"):
            with self.subTest(key=key):
                self.assertIn(key, self.manifest)
        self.assertEqual(self.manifest["display"], "standalone")
        self.assertEqual(self.manifest["lang"], "bn")

    def test_icons_exist_and_are_real_png(self):
        for icon in self.manifest["icons"]:
            path = WEB / icon["src"]
            with self.subTest(icon=icon["src"]):
                self.assertTrue(path.is_file())
                width, height = png_size(path.read_bytes())
                expected = int(icon["sizes"].split("x")[0])
                self.assertEqual((width, height), (expected, expected))

    def test_has_maskable_icon(self):
        purposes = {icon.get("purpose") for icon in self.manifest["icons"]}
        self.assertIn("maskable", purposes)

    def test_apple_touch_icon_size(self):
        width, height = png_size((WEB / "icons" / "icon-180.png").read_bytes())
        self.assertEqual((width, height), (180, 180))


class WorkerTest(unittest.TestCase):
    def setUp(self):
        self.src = (WORKER / "index.js").read_text(encoding="utf-8")

    def test_has_three_endpoints(self):
        for route in ("/api/health", "/api/chat", "/api/messages"):
            with self.subTest(route=route):
                self.assertIn(route, self.src)

    def test_token_only_from_env(self):
        self.assertIn("env.GITHUB_TOKEN", self.src)
        self.assertNotIn("Bearer ghp_", self.src)

    def test_passcode_guard(self):
        self.assertIn("APP_PASSCODE", self.src)
        self.assertIn("x-passcode", self.src.lower())

    def test_posts_mesh_comment(self):
        self.assertIn("@mesh", self.src)


@unittest.skipUnless(shutil.which("node"), "node ইনস্টল নেই")
class NodeSideTest(unittest.TestCase):
    """JS অংশ আসলেই চালিয়ে দেখা হয় (নকল GitHub দিয়ে)।"""

    def _run(self, *args: str, cwd: Path = ROOT) -> str:
        out = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=180)
        self.assertEqual(out.returncode, 0, (out.stdout or "") + (out.stderr or ""))
        return out.stdout

    def test_worker_behaviour(self):
        out = self._run("node", "tests/js/worker_check.mjs")
        self.assertIn("Worker সব পরীক্ষায় পাস", out)

    def test_markdown_renderer(self):
        out = self._run("node", "--test", "tests/md.test.mjs", cwd=WEB)
        self.assertIn("fail 0", out)

    def test_dom_smoke(self):
        # jsdom না থাকলে স্ক্রিপ্ট নিজেই বাদ দেয় (exit 0)
        out = self._run("node", "tests/js/dom_check.mjs")
        self.assertTrue("সব DOM পরীক্ষা পাস" in out or "jsdom নেই" in out, out)


if __name__ == "__main__":
    unittest.main()
