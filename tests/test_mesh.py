"""মেশের মূল পরীক্ষা — ইন্টারনেট বা API key ছাড়াই চলে।

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mesh.adapters import CliAdapter  # noqa: E402
from mesh.chat import Store  # noqa: E402
from mesh.config import AgentSpec, MeshConfig  # noqa: E402
from mesh.router import Router  # noqa: E402
from mesh.textutil import find_mentions, looks_like_quota_problem  # noqa: E402


class FakeRunner:
    """সত্যিকারের কমান্ড চালায় না — শুধু উত্তর ফিরিয়ে দেয়।"""

    def __init__(self, script=None):
        self.calls = []
        self.script = script or {}

    def __call__(self, cmd, env, cwd, timeout):
        self.calls.append((tuple(cmd), dict(env)))
        name = cmd[0]
        resp = self.script.get(name)
        if callable(resp):
            return resp(cmd, env, len(self.calls))
        if isinstance(resp, tuple):
            return resp
        return 0, f"{name} বলছে: ঠিক আছে", ""

    def names(self):
        return [c[0][0] for c in self.calls]


def make_router(runner=None, tmp=None, **kwargs):
    config = MeshConfig.load()
    store = Store(Path(tmp or tempfile.mkdtemp()) / "transcript.jsonl")
    return Router(config, runner=runner or FakeRunner(), store=store, workdir=".", **kwargs)


class TextUtilTest(unittest.TestCase):
    def test_find_mentions_keeps_order_and_filters(self):
        text = "@Claude দেখো, আর @cline কে বলো — @unknown বাদ"
        self.assertEqual(find_mentions(text, ["claude", "cline"]), ["claude", "cline"])

    def test_quota_markers(self):
        self.assertTrue(looks_like_quota_problem("Error 429: rate limit exceeded"))
        self.assertFalse(looks_like_quota_problem("all tests passed"))


class ConfigTest(unittest.TestCase):
    def test_team_loaded(self):
        config = MeshConfig.load()
        names = config.names()
        for expected in ("opencode", "cline", "claude", "hermes", "openhands"):
            self.assertIn(expected, names)

    def test_hermes_is_worker_not_manager(self):
        hermes = MeshConfig.load().get("hermes")
        self.assertEqual(hermes.kind, "cli")
        self.assertTrue(hermes.has_role("worker"))

    def test_openhands_not_in_group_chat(self):
        config = MeshConfig.load()
        self.assertNotIn("openhands", [a.name for a in config.chat_agents()])


class ClassifyTest(unittest.TestCase):
    def test_mention_wins(self):
        router = make_router()
        self.assertEqual(router.classify("@claude এই আর্কিটেকচার দেখো"), ["claude"])

    def test_keyword_match(self):
        router = make_router()
        self.assertEqual(router.classify("এই bug টা ঠিক করো"), ["opencode"])

    def test_default_when_nothing_matches(self):
        router = make_router()
        self.assertEqual(router.classify("আজ কেমন আছো"), ["opencode"])


class DirectModeTest(unittest.TestCase):
    def test_calls_only_one_agent(self):
        runner = FakeRunner()
        router = make_router(runner)
        replies = router.direct("এই bug টা ঠিক করো")
        self.assertEqual(runner.names(), ["opencode"])
        self.assertTrue(replies[0].ok)
        self.assertEqual(router.calls, 1)

    def test_falls_back_when_first_fails(self):
        runner = FakeRunner({"opencode": (1, "", "boom")})
        router = make_router(runner)
        replies = router.direct("এই bug টা ঠিক করো")
        self.assertTrue(any(r.ok for r in replies))
        self.assertGreaterEqual(len(runner.calls), 2)


class GroupModeTest(unittest.TestCase):
    def test_fanout_to_all_chat_agents(self):
        runner = FakeRunner()
        router = make_router(runner)
        router.group("হাই")
        self.assertCountEqual(runner.names(), ["opencode", "cline", "claude", "hermes"])
        self.assertNotIn("openhands", runner.names())

    def test_mention_triggers_reply_in_next_round(self):
        def hermes(cmd, env, n):
            return 0, "আমি হের্মস — @claude তুমি কী বলো?", ""

        runner = FakeRunner({"hermes": hermes})
        router = make_router(runner)
        router.group("হাই")
        self.assertEqual(runner.names().count("claude"), 2)  # রাউন্ড ১ + ডাকা হয়ে রাউন্ড ২

    def test_round_cap_protects_against_loop(self):
        def pingpong(cmd, env, n):
            other = "cline" if cmd[0] == "opencode" else "opencode"
            return 0, f"@{other} আবার বলো", ""

        runner = FakeRunner({"opencode": pingpong, "cline": pingpong})
        router = make_router(runner)
        router.group("হাই")
        self.assertLessEqual(router.calls, router.config.settings.max_calls_per_run)

    def test_budget_stops_everything(self):
        runner = FakeRunner()
        router = make_router(runner)
        router.config.settings.max_calls_per_run = 2
        router.group("হাই")
        self.assertEqual(router.calls, 2)

    def test_pair_limit(self):
        router = make_router()
        router.config.settings.max_pair_calls = 2
        for _ in range(5):
            router.call("cline", "আবার বলো", sender="opencode")
        self.assertEqual(router.call("cline", "আবারও", sender="opencode").ok, False)
        self.assertEqual(router.pair_calls[("opencode", "cline")], 2)
        self.assertEqual(router.calls, 2)


class KeyRotationTest(unittest.TestCase):
    def test_second_key_used_after_quota_error(self):
        attempts = []

        def runner(cmd, env, cwd, timeout):
            attempts.append(env.get("OPENROUTER_API_KEY"))
            if len(attempts) == 1:
                return 1, "", "429 rate limit exceeded"
            return 0, "ঠিক আছে", ""

        spec = AgentSpec(
            name="claude",
            command=["claude", "-p", "{message}"],
            env={"ANTHROPIC_AUTH_TOKEN": "$OPENROUTER_API_KEY"},
            keys=["OPENROUTER_API_KEY"],
        )
        adapter = CliAdapter(
            spec, runner=runner, environ={"OPENROUTER_API_KEY": "key-1", "OPENROUTER_API_KEY_2": "key-2"}
        )
        reply = adapter.send("হাই")
        self.assertTrue(reply.ok)
        self.assertEqual(attempts, ["key-1", "key-2"])


class DryRunTest(unittest.TestCase):
    def test_dry_run_never_spawns(self):
        runner = FakeRunner()
        router = make_router(runner, dry_run=True)
        replies = router.group("হাই")
        self.assertEqual(runner.calls, [])
        self.assertTrue(all("[dry-run]" in r.text for r in replies))


class StoreTest(unittest.TestCase):
    def test_append_and_count(self):
        store = Store(Path(tempfile.mkdtemp()) / "t.jsonl")
        store.append({"agent": "opencode", "text": "হাই"})
        self.assertEqual(store.today_count("opencode"), 1)
        self.assertEqual(len(store.recent()), 1)


if __name__ == "__main__":
    unittest.main()


class DoctorTest(unittest.TestCase):
    def _checks(self, environ=None, which=None):
        from mesh.doctor import run_doctor

        config = MeshConfig.load()
        store_path = Path(tempfile.mkdtemp()) / "t.jsonl"
        return {
            c.item: c
            for c in run_doctor(
                config,
                environ=environ or {},
                which=which or (lambda name: None),
                store_path=store_path,
            )
        }

    def test_missing_cli_is_warning_not_failure(self):
        checks = self._checks()
        self.assertEqual(checks["🧑‍💻 OpenCode"].status, "warn")
        self.assertIn("ইনস্টল নেই", checks["🧑‍💻 OpenCode"].detail)

    def test_missing_key_is_failure(self):
        checks = self._checks()
        self.assertEqual(checks["claude keys"].status, "fail")

    def test_key_and_binary_found(self):
        checks = self._checks(
            environ={"OPENROUTER_API_KEY": "sk-or-secret", "OPENROUTER_API_KEY_2": "sk-or-two"},
            which=lambda name: "/usr/bin/" + name,
        )
        self.assertEqual(checks["claude keys"].status, "ok")
        self.assertIn("2টা", checks["claude keys"].detail)
        self.assertNotIn("sk-or-secret", checks["claude keys"].detail)  # key লুকানো থাকে
        self.assertEqual(checks["🧑‍💻 OpenCode"].status, "ok")

    def test_store_is_writable(self):
        self.assertEqual(self._checks()["store"].status, "ok")
