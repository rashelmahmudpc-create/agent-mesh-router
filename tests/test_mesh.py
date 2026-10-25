"""মেশের মূল পরীক্ষা — ইন্টারনেট বা API key ছাড়াই চলে।

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent

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


def all_enabled_config() -> MeshConfig:
    """টেস্টের জন্য সব এজেন্ট চালু — আসল ডিফল্ট আলাদা টেস্টে যাচাই হয়।"""
    config = MeshConfig.load()
    for agent in config.agents:
        agent.enabled = True
    return config


def make_router(runner=None, tmp=None, config=None, **kwargs):
    config = config or all_enabled_config()
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
        names = [a.name for a in config.agents]
        for expected in ("opencode", "cline", "claude", "hermes", "openhands"):
            self.assertIn(expected, names)

    def test_hermes_is_worker_not_manager(self):
        hermes = MeshConfig.load().get("hermes")
        self.assertEqual(hermes.kind, "cli")
        self.assertTrue(hermes.has_role("worker"))

    def test_openhands_not_in_group_chat(self):
        config = all_enabled_config()
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


class IssueHallTest(unittest.TestCase):
    def _gh_runner(self, payload, capture=None):
        import json as _json

        def runner(cmd, env, cwd, timeout):
            if capture is not None:
                capture.append(cmd)
            return 0, _json.dumps(payload), ""

        return runner

    def test_fetch_hall_reads_comments(self):
        from mesh.issue import fetch_hall

        payload = {
            "title": "গ্রুপ চ্যাট",
            "body": "শুরু করো",
            "comments": [
                {"author": {"login": "zayan"}, "body": "@mesh হাই সবাই"},
                {"author": {"login": "bot"}, "body": "OpenCode বলছে: ঠিক আছে"},
            ],
        }
        hall = fetch_hall(7, runner=self._gh_runner(payload))
        self.assertIn("@zayan", hall)
        self.assertIn("OpenCode", hall)
        self.assertIn("গ্রুপ চ্যাট", hall)

    def test_fetch_hall_redacts_secrets(self):
        from mesh.issue import fetch_hall

        payload = {"title": "x", "body": "", "comments": [
            {"author": {"login": "a"}, "body": "key sk-or-v1-abcdef1234567890abc লিক হয়েছে"}]}
        hall = fetch_hall(1, runner=self._gh_runner(payload))
        self.assertNotIn("sk-or-v1-abcdef1234567890abc", hall)
        self.assertIn("REDACTED", hall)

    def test_fetch_hall_survives_gh_failure(self):
        from mesh.issue import fetch_hall

        def bad(cmd, env, cwd, timeout):
            return 1, "", "gh: not found"

        self.assertEqual(fetch_hall(1, runner=bad), "")

    def test_post_comment_writes_marker_and_redacts(self):
        from mesh.issue import post_comment

        captured = []
        ok = post_comment(
            5, "opencode", "🧑‍💻 OpenCode", "উত্তর — key sk-ant-abcdefgh12345678",
            runner=self._gh_runner({}, captured),
        )
        self.assertTrue(ok)
        body = captured[0][captured[0].index("--body") + 1]
        self.assertIn("mesh:opencode", body)
        self.assertNotIn("sk-ant-abcdefgh12345678", body)

    def test_post_comment_dry_run_does_not_call_gh(self):
        from mesh.issue import post_comment

        captured = []
        self.assertTrue(post_comment(5, "cline", "Cline", "হাই", runner=self._gh_runner({}, captured), dry_run=True))
        self.assertEqual(captured, [])


class GroupHistoryTest(unittest.TestCase):
    def test_history_reaches_the_prompt(self):
        runner = FakeRunner()
        router = make_router(runner)
        router.group("নতুন প্রশ্ন", history="- @zayan: আগের কথা")
        joined = " ".join(" ".join(cmd) for cmd, _env in runner.calls)
        self.assertIn("আগের কথা", joined)
        self.assertIn("হলঘরে", joined)

    def test_direct_mode_ignores_history(self):
        runner = FakeRunner()
        router = make_router(runner)
        router.direct("এই bug ঠিক করো")
        joined = " ".join(" ".join(cmd) for cmd, _env in runner.calls)
        self.assertNotIn("আগের কথা", joined)


class RedactTest(unittest.TestCase):
    def test_masks_common_key_shapes(self):
        from mesh.issue import redact

        text = " ".join([
            "sk-or-v1-aaaaaaaaaaaaaaaaaaaa",
            "ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "AIzaSyAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "xai-aaaaaaaaaaaaaaaaaaaa",
            "Bearer abcdefghijklmnopqrstuvwxyz",
        ])
        out = redact(text)
        for secret in text.split():
            if secret != "Bearer":
                self.assertNotIn(secret, out)
        self.assertEqual(out.count("«REDACTED»"), 5)


class GhEnvTest(unittest.TestCase):
    def test_gh_calls_get_a_real_environment(self):
        from mesh.issue import fetch_hall, post_comment

        seen = []

        def runner(cmd, env, cwd, timeout):
            seen.append(dict(env))
            return 0, "{}", ""

        fetch_hall(1, runner=runner)
        post_comment(1, "opencode", "OpenCode", "হাই", runner=runner)
        self.assertTrue(seen)
        for env in seen:
            self.assertIn("PATH", env, "gh চালানোর জন্য PATH দরকার")


class FreeModelTest(unittest.TestCase):
    def test_default_model_expansion(self):
        from mesh.keys import expand_env_value

        self.assertEqual(expand_env_value("$CLAUDE_MODEL:-openrouter/free", {}), "openrouter/free")
        self.assertEqual(
            expand_env_value("$CLAUDE_MODEL:-openrouter/free", {"CLAUDE_MODEL": "z-ai/glm-5.2:free"}),
            "z-ai/glm-5.2:free",
        )
        # খালি ভেরিয়েবল মানে ডিফল্টই ব্যবহার হবে
        self.assertEqual(expand_env_value("$CLAUDE_MODEL:-openrouter/free", {"CLAUDE_MODEL": ""}), "openrouter/free")
        # ডিফল্ট ছাড়া পুরনো আচরণ অপরিবর্তিত
        self.assertEqual(expand_env_value("$OPENROUTER_API_KEY", {}), "")

    def test_claude_works_without_money(self):
        """কোনো CLAUDE_MODEL সেট না করলেও claude ফ্রি মডেলে চলে।"""
        agent = MeshConfig.load().get("claude")
        from mesh.keys import expand_env_value

        resolved = expand_env_value(agent.env["ANTHROPIC_MODEL"], {})
        self.assertIn("free", resolved.lower())

    def test_doctor_reports_model(self):
        from mesh.doctor import run_doctor

        checks = {
            c.item: c
            for c in run_doctor(
                MeshConfig.load(), environ={}, which=lambda n: None,
                store_path=Path(tempfile.mkdtemp()) / "t.jsonl",
            )
        }
        self.assertIn("claude model", checks)
        self.assertIn("ফ্রি", checks["claude model"].detail)

    def test_base_env_keeps_empty_literal_but_skips_missing_var(self):
        attempts = []

        def runner(cmd, env, cwd, timeout):
            attempts.append(dict(env))
            return 0, "ok", ""

        spec = AgentSpec(
            name="claude",
            command=["claude", "-p", "{message}"],
            env={"ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": "$NOPE_MISSING"},
        )
        CliAdapter(spec, runner=runner, environ={}).send("হাই")
        self.assertEqual(attempts[0].get("ANTHROPIC_API_KEY"), "")  # literal "" থাকবে
        self.assertNotIn("ANTHROPIC_AUTH_TOKEN", attempts[0])      # নেই → সেট হবে না


class ExitCodeTest(unittest.TestCase):
    """CI তে লাল ✅ এড়াতে ডিফল্টে exit 0; --strict দিলে 1."""

    def test_group_dry_run_is_green(self):
        from mesh import cli

        code = cli.main(["হাই", "--mode", "group", "--dry-run"])
        self.assertEqual(code, 0)

    def test_doctor_is_green_by_default_and_strict_fails(self):
        from mesh import cli

        self.assertEqual(cli.main(["--doctor"]), 0)
        env_ok = {"PATH": "/usr/bin"}
        from mesh.doctor import run_doctor, print_checks

        checks = run_doctor(
            MeshConfig.load(), environ=env_ok, which=lambda n: None,
            store_path=Path(tempfile.mkdtemp()) / "t.jsonl",
        )
        self.assertEqual(print_checks(checks), 0)
        self.assertEqual(print_checks(checks, strict=True), 1)


class WorkflowFileTest(unittest.TestCase):
    def test_workflow_has_summary_and_status_issue(self):
        text = (ROOT / ".github" / "workflows" / "mesh.yml").read_text(encoding="utf-8")
        self.assertIn("GITHUB_STEP_SUMMARY", text)
        self.assertIn("mesh-status", text)
        self.assertIn("doctor.txt", text)
        # set -e এর সাথে [ ... ] && ... থাকলে জব মরে যায় — আর রাখা যাবে না
        self.assertNotIn("set -euo pipefail", text)

    def test_workflow_does_not_require_package_json(self):
        text = (ROOT / ".github" / "workflows" / "mesh.yml").read_text(encoding="utf-8")
        self.assertNotIn("cache: npm", text)

    def test_only_trusted_people_can_trigger_from_issue_comment(self):
        text = (ROOT / ".github" / "workflows" / "mesh.yml").read_text(encoding="utf-8")
        self.assertIn("author_association", text)
        self.assertIn("OWNER", text)


class EmptyReplyTest(unittest.TestCase):
    def test_exit_zero_with_empty_output_is_failure(self):
        spec = AgentSpec(name="claude", command=["claude", "-p", "{message}"])
        adapter = CliAdapter(spec, runner=lambda c, e, w, t: (0, "   ", ""))
        reply = adapter.send("হাই")
        self.assertFalse(reply.ok)
        self.assertTrue(reply.meta.get("empty"))
        self.assertIn("খালি", reply.text)


class CommandEnvTest(unittest.TestCase):
    def test_command_supports_default_model(self):
        spec = AgentSpec(
            name="opencode",
            command=["opencode", "run", "--model", "$OPENCODE_MODEL:-opencode/deepseek-v4.1-flash-free", "{message}"],
        )
        adapter = CliAdapter(spec, dry_run=True)
        self.assertIn("opencode/deepseek-v4.1-flash-free", adapter._cmd("হাই"))

        custom = CliAdapter(spec, dry_run=True, environ={"OPENCODE_MODEL": "my/model"})
        self.assertIn("my/model", custom._cmd("হাই"))

    def test_only_verified_agents_are_on(self):
        config = MeshConfig.load()
        active = [a.name for a in config.enabled()]
        # যাচাই করা এজেন্ট চালু
        for name in ("opencode", "claude", "hermes"):
            self.assertIn(name, active)
        # যাচাই হয়নি (OpenHands org/mention) — বন্ধ
        self.assertNotIn("openhands", active)


class DoctorHonestyTest(unittest.TestCase):
    def test_disabled_agents_do_not_block(self):
        from mesh.doctor import run_doctor

        checks = run_doctor(
            MeshConfig.load(),
            environ={"GH_TOKEN": "x", "OPENROUTER_API_KEY": "sk-or-test"},
            which=lambda n: "/bin/" + n,
            store_path=Path(tempfile.mkdtemp()) / "t.jsonl",
        )
        # key দেওয়া আছে → কোনো ব্যর্থতা নেই; বন্ধ এজেন্ট শুধু সতর্কতা
        fails = [c.item for c in checks if c.status == "fail"]
        self.assertEqual(fails, [])
        by_item = {c.item: c for c in checks}
        self.assertEqual(by_item["🖐️ OpenHands"].status, "warn")


class AnsiAndFallbackTest(unittest.TestCase):
    def test_ansi_is_stripped_from_replies(self):
        from mesh.textutil import strip_ansi

        messy = "◈[0m\n> build · model\n◈[91m◈[1mError: ◈[0mFree usage limit reached"
        clean = strip_ansi(messy)
        self.assertNotIn("◈", clean)
        self.assertIn("Free usage limit reached", clean)

    def test_failure_text_has_no_escape_codes(self):
        spec = AgentSpec(name="opencode", command=["opencode", "run", "{message}"])
        adapter = CliAdapter(spec, runner=lambda c, e, w, t: (1, "", "◈[91mError: ◈[0mboom"))
        reply = adapter.send("হাই")
        self.assertFalse(reply.ok)
        self.assertNotIn("◈", reply.text)

    def test_fallback_runs_when_limit_reached(self):
        seen = []

        def runner(cmd, env, cwd, timeout):
            seen.append(cmd)
            if "--fallback-model" in cmd:
                return 0, "fallback উত্তর", ""
            return 1, "", "Free usage limit reached"

        spec = AgentSpec(
            name="opencode",
            command=["opencode", "run", "{message}"],
            fallback_commands=[["opencode", "run", "--fallback-model", "{message}"]],
        )
        reply = CliAdapter(spec, runner=runner).send("হাই")
        self.assertTrue(reply.ok)
        self.assertEqual(reply.text, "fallback উত্তর")
        self.assertEqual(len(seen), 2)

    def test_no_fallback_on_unrelated_error(self):
        seen = []

        def runner(cmd, env, cwd, timeout):
            seen.append(cmd)
            return 1, "", "syntax error in your code"

        spec = AgentSpec(
            name="opencode",
            command=["opencode", "run", "{message}"],
            fallback_commands=[["opencode", "run", "--alt", "{message}"]],
        )
        reply = CliAdapter(spec, runner=runner).send("হাই")
        self.assertFalse(reply.ok)
        self.assertEqual(len(seen), 1)  # অকারণে দ্বিতীয়বার চালায়নি

    def test_empty_output_moves_to_fallback(self):
        seen = []

        def runner(cmd, env, cwd, timeout):
            seen.append(cmd)
            if "--alt" in cmd:
                return 0, "এবার উত্তর আছে", ""
            return 0, "   ", ""

        spec = AgentSpec(
            name="claude",
            command=["claude", "-p", "{message}"],
            fallback_commands=[["claude", "--alt", "{message}"]],
        )
        reply = CliAdapter(spec, runner=runner).send("হাই")
        self.assertTrue(reply.ok)
        self.assertEqual(len(seen), 2)

    def test_doctor_step_receives_secrets(self):
        """ডক্টর step এ secret না থাকলে ভুল করে 'key নেই' বলে — এটা যেন না হয়।"""
        text = (ROOT / ".github" / "workflows" / "mesh.yml").read_text(encoding="utf-8")
        doctor_block = text.split("- name: Doctor")[1].split("- name:")[0]
        self.assertIn("OPENROUTER_API_KEY", doctor_block)


class AutoTriggerTest(unittest.TestCase):
    """ব্যবহারকারীকে ক্লিক করতে না হয় — অটো ট্রিগার ঠিক আছে কি না।"""

    def _text(self):
        return (ROOT / ".github" / "workflows" / "mesh.yml").read_text(encoding="utf-8")

    def test_push_marker_triggers(self):
        text = self._text()
        self.assertIn('".mesh-run"', text)
        self.assertIn("paths:", text)

    def test_schedule_triggers(self):
        self.assertIn("schedule:", self._text())
        self.assertIn("cron:", self._text())

    def test_defaults_work_without_manual_inputs(self):
        text = self._text()
        self.assertIn("inputs.message || github.event.comment.body ||", text)
        self.assertIn("inputs.mode || 'group'", text)

    def test_guard_skips_when_no_key(self):
        text = self._text()
        self.assertIn("steps.guard.outputs.skip", text)
        self.assertIn("খরচ বাঁচাতে", text)

    def test_marker_file_exists(self):
        self.assertTrue((ROOT / ".mesh-run").exists())


class CleanReplyTest(unittest.TestCase):
    def test_noise_and_reasoning_removed(self):
        from mesh.textutil import clean_reply

        raw = (
            "⚠ tirith security scanner enabled but not available — command scanning will use pattern matching only\n\n"
            "┌─ Reasoning ───────────┐\nThe user is asking...\n└───────────────────────┘\n"
            "আমি Hermes Agent, প্রস্তুত আছি।\n"
        )
        self.assertEqual(clean_reply(raw), "আমি Hermes Agent, প্রস্তুত আছি।")

    def test_only_noise_becomes_empty(self):
        from mesh.textutil import clean_reply

        self.assertEqual(clean_reply("⚠ tirith security scanner enabled but not available"), "")

    def test_adapter_uses_clean_reply(self):
        spec = AgentSpec(name="hermes", command=["hermes", "chat", "-q", "{message}"])
        noisy = "⚠ tirith security scanner enabled but not available\n\nআসল উত্তর"
        adapter = CliAdapter(spec, runner=lambda c, e, w, t: (0, noisy, ""))
        reply = adapter.send("হাই")
        self.assertTrue(reply.ok)
        self.assertEqual(reply.text, "আসল উত্তর")


class FreeChainTest(unittest.TestCase):
    def test_unavailable_for_free_triggers_next_model(self):
        from mesh.textutil import looks_like_quota_problem

        self.assertTrue(looks_like_quota_problem(
            "HTTP 404: This model is unavailable for free. The paid version is available now"))

    def test_nested_default_expansion(self):
        from mesh.keys import expand_env_value

        self.assertEqual(expand_env_value("$A:-$B", {"B": "from-b"}), "from-b")
        self.assertEqual(expand_env_value("$A:-$B", {"A": "top"}), "top")

    def test_agents_have_multi_step_free_chain(self):
        config = MeshConfig.load()
        for name in ("hermes", "claude"):
            agent = config.get(name)
            self.assertGreaterEqual(len(agent.fallback_commands), 2, f"{name}: অন্তত ২টা বিকল্প মডেল দরকার")

    def test_chain_moves_to_next_model_when_first_is_paid(self):
        calls = []

        def runner(cmd, env, cwd, timeout):
            calls.append(cmd)
            if "free/second" in cmd:
                return 0, "দ্বিতীয় মডেলের উত্তর", ""
            return 1, "", "404 This model is unavailable for free"

        agent = MeshConfig.load().get("hermes")
        from mesh.adapters import CliAdapter

        reply = CliAdapter(
            agent, runner=runner,
            environ={"OPENROUTER_API_KEY": "k", "FREE_M1": "free/first", "FREE_M2": "free/second"},
        ).send("হাই")
        self.assertTrue(reply.ok)
        self.assertEqual(reply.text, "দ্বিতীয় মডেলের উত্তর")
        self.assertGreaterEqual(len(calls), 2)


class FreeModelDiscoveryTest(unittest.TestCase):
    def _m(self, mid, price, ctx, tools=True):
        return {
            "id": mid,
            "pricing": {"prompt": price, "completion": price},
            "context_length": ctx,
            "supported_parameters": ["tools", "temperature"] if tools else ["temperature"],
        }

    def test_picks_biggest_free_tool_model(self):
        from mesh.models import pick_free_model

        models = [
            self._m("paid/big", "0.000003", 1_000_000),
            self._m("free/small", "0", 32_000),
            self._m("free/good", "0", 262_000),
            self._m("free/bigger-no-tools", "0", 900_000, tools=False),
        ]
        self.assertEqual(pick_free_model(models), "free/good")

    def test_returns_none_when_nothing_qualifies(self):
        from mesh.models import pick_free_model

        self.assertIsNone(pick_free_model([self._m("paid/x", "0.000002", 500_000)]))
        self.assertIsNone(pick_free_model([]))

    def test_price_zero_variants(self):
        from mesh.models import pick_free_model

        models = [self._m("free/a", "0.0", 100_000), self._m("free/b", "0.000000", 100_000)]
        self.assertIn(pick_free_model(models), {"free/a", "free/b"})

    def test_cli_handles_no_network(self):
        from mesh import cli

        self.assertEqual(cli.main(["--free-model"]), 1)


class WorkflowShellHygieneTest(unittest.TestCase):
    """bash এ ভুল escape (tr '\\n') দিয়ে মডেলের নাম নষ্ট হয়েছিল — আর যেন না হয়।"""

    def test_no_literal_double_backslash_n_in_tr(self):
        text = (ROOT / ".github" / "workflows" / "mesh.yml").read_text(encoding="utf-8")
        self.assertNotIn("tr '\\\\n'", text)
        self.assertNotIn("tr '\\n'", text)

    def test_free_model_file_is_ignored(self):
        self.assertIn("free-model.txt", (ROOT / ".gitignore").read_text(encoding="utf-8"))
