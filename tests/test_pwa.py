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
    "api.github.com",  # GitHub সরাসরি মোড (Worker ছাড়া) — ব্রাউজার থেকে Issue পড়া/লেখা
    "api.groq.com",  # ⚡ দ্রুত মোড — ব্রাউজার থেকে সরাসরি AI API
    "generativelanguage.googleapis.com",  # ⚡ দ্রুত মোড (Gemini)
    "openrouter.ai",  # ⚡ দ্রুত মোড (OpenRouter)
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



class FastLaneTest(unittest.TestCase):
    """⚡ Cloudflare-এর দ্রুত লেন — Actions ছাড়াই ৩–৮ সেকেন্ডে উত্তর।"""

    def setUp(self):
        self.worker = (ROOT / "worker" / "index.js").read_text(encoding="utf-8")

    def test_direct_model_calls_exist(self):
        for url in (
            "api.groq.com",
            "openrouter.ai/api/v1/chat/completions",
            "generativelanguage.googleapis.com",
        ):
            self.assertIn(url, self.worker, f"{url} কল নেই")

    def test_four_agents_answer_in_parallel(self):
        self.assertIn("PERSONAS", self.worker)
        self.assertIn("Promise.all", self.worker)
        for name in ("OpenCode", "Claude Code", "Hermes", "OpenHands"):
            self.assertIn(name, self.worker, f"{name} persona নেই")

    def test_fast_lane_can_be_switched_off(self):
        self.assertIn('"off"', self.worker)
        self.assertIn("FAST", self.worker)
        # key না থাকলে নিজে থেকেই পুরনো পথে
        self.assertIn("fastReady", self.worker)

    def test_answers_still_reach_the_issue(self):
        self.assertIn("postAnswers", self.worker)
        self.assertIn("waitUntil", self.worker)  # পেছনে পোস্ট, গতি কমে না

    def test_fast_lane_never_posts_at_mesh(self):
        """দ্রুত লেনের comment যেন Actions রান না ডাকে (@mesh / মার্কার যাচাই)।"""
        block = self.worker.split("async function handleFastChat")[1].split("async function handleChat")[0]
        self.assertNotIn("@mesh ", block)
        self.assertIn("<!-- mesh:", self.worker)

    def test_deploy_workflow_skips_without_secrets(self):
        wf = (ROOT / ".github" / "workflows" / "worker.yml").read_text(encoding="utf-8")
        self.assertIn("CF_API_TOKEN", wf)
        self.assertIn("ok=false", wf)  # কাজ করা key না থাকলে চুপচাপ বাদ
        self.assertIn("wrangler", wf)



class AutoDeployTest(unittest.TestCase):
    """☁️ স্যার কিছু করবেন না — workflow নিজেই কাজ করা key খুঁজে ডিপ্লয় করবে।"""

    def setUp(self):
        self.wf = (ROOT / ".github" / "workflows" / "worker.yml").read_text(encoding="utf-8")
        self.app = (APP / "index.html").read_text(encoding="utf-8")

    def test_any_key_name_and_type_works(self):
        """নাম যা-ই হোক, API Token হোক বা Global API Key — সব চেষ্টা করে।"""
        for name in ("CF_API_KEY", "CF_API_TOKEN", "CLOUDFLARE_API_KEY",
                     "CLOUDFLARE_API_TOKEN", "ADMISSIONSKY_CLOUDFLARE_API_KEY"):
            self.assertIn(f"secrets.{name}", self.wf, f"{name} চেনে না")
        self.assertIn("X-Auth-Key", self.wf)            # Global API Key
        self.assertIn("/user/tokens/verify", self.wf)    # API Token
        self.assertIn("for name, value in CANDIDATES", self.wf)  # একটার পর একটা চেষ্টা

    def test_models_fall_back_within_a_provider(self):
        """মডেলের নাম পুরনো হয়ে গেলে (404) পরের মডেল চেষ্টা করে।"""
        worker = (ROOT / "worker" / "index.js").read_text(encoding="utf-8")
        self.assertIn("models:", worker)
        self.assertIn("for (const model of models)", worker)
        self.assertIn("gemini-2.5-flash", worker)
        self.assertIn("OpenRouter key আছে", worker)  # দ্বিতীয় key ব্যবহার

    def test_email_is_used_for_global_key(self):
        for name in ("CF_EMAIL", "CLOUDFLARE_EMAIL", "ADMISSIONSKY_CLOUDFLARE_EMAIL"):
            self.assertIn(f"secrets.{name}", self.wf, f"{name} চেনে না")

    def test_keys_are_masked_and_never_printed(self):
        self.assertIn("::add-mask::", self.wf)
        for leak in ('echo "$CLOUDFLARE_API_KEY"', 'echo "$CLOUDFLARE_API_TOKEN"'):
            self.assertNotIn(leak, self.wf, f"key লিক হতে পারে: {leak}")

    def test_keys_are_pushed_to_the_worker(self):
        for name in ("OPENROUTER_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY"):
            self.assertIn(f"put {name}", self.wf, f"{name} Worker-এ বসে না")

    def test_url_is_written_for_the_app(self):
        self.assertIn("workers/subdomain", self.wf)
        self.assertIn("docs/app/server.json", self.wf)
        self.assertIn("/api/health", self.wf)
        self.assertIn("contents: write", self.wf)

    def test_report_reaches_the_readable_issue(self):
        self.assertIn("issues: write", self.wf)
        self.assertIn("gh issue comment", self.wf)

    def test_retries_itself_every_six_hours(self):
        self.assertIn("schedule:", self.wf)
        self.assertIn("cron:", self.wf)

    def test_app_reads_the_url_by_itself(self):
        self.assertIn("server.json", self.app)
        # নিজে বেছে নিলে (github/fast) ছোঁবে না, নইলে Worker আগে
        self.assertIn("cfg.route==='github'||cfg.route==='fast'", self.app)

    def test_worker_wins_over_the_slow_github_path(self):
        """স్క্রিনশটের বাগ: Worker থাকা সত্ত্বেও অ্যাপ GitHub-এর ১৫০s পথে যাচ্ছিল।"""
        self.assertIn("const workerOn=", self.app)
        self.assertIn("const isGh=()=>!workerOn()", self.app)
        self.assertIn("const fastOn=()=>!workerOn()", self.app)
        self.assertIn("routeName", self.app)
        self.assertIn("কোন পথে কথা বলবে", self.app)
