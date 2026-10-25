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


class StreamingReplyTest(unittest.TestCase):
    """on_reply: উত্তর তৈরি হওয়ামাত্র callback ডাকে — Issue-এ সাথে সাথে comment যায়,
    তাই অ্যাপে সবচেয়ে দ্রুত এজেন্টের উত্তর আগে দেখা যায় (সবার জন্য অপেক্ষা নয়)।"""

    def test_direct_emits_each_reply(self):
        seen = []
        router = make_router(FakeRunner(), on_reply=seen.append)
        replies = router.direct("এই bug টা ঠিক করো")
        self.assertEqual(len(seen), len(replies))
        self.assertIs(seen[0], replies[0])

    def test_group_emits_every_agent(self):
        seen = []
        router = make_router(FakeRunner(), on_reply=seen.append)
        replies = router.group("হাই")
        self.assertEqual(len(seen), len(replies))
        self.assertCountEqual([r.agent for r in seen], [r.agent for r in replies])

    def test_callback_error_does_not_break_run(self):
        def boom(_reply):
            raise RuntimeError("network")

        router = make_router(FakeRunner(), on_reply=boom)
        replies = router.group("হাই")
        self.assertTrue(any(r.ok for r in replies))


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

    def test_openhands_is_tested_live_once_a_day(self):
        """OPENHANDS_API_KEY আসলেই কাজ করে কি না — workflow নিজেই দিনে একবার যাচাই করবে।"""
        text = (ROOT / ".github" / "workflows" / "mesh.yml").read_text(encoding="utf-8")
        self.assertIn("OpenHands live check", text)
        self.assertIn("--openhands", text)
        self.assertIn(".mesh-openhands-ok", text)
        self.assertIn("openhands.txt", text)

    def test_hermes_gets_enough_turns_and_free_models(self):
        """--max-turns 3-এ Hermes উত্তর দেওয়ার আগেই থেমে যেত।"""
        data = (ROOT / "config" / "agents.json").read_text(encoding="utf-8")
        import json as _json

        hermes = [a for a in _json.loads(data)["agents"] if a["name"] == "hermes"][0]
        for cmd in [hermes["command"], *hermes["fallback_commands"]]:
            turns = int(cmd[cmd.index("--max-turns") + 1])
            self.assertGreaterEqual(turns, 6)
            self.assertIn("openrouter", " ".join(cmd))

    def test_hermes_reasoning_box_is_turned_off_in_ci(self):
        text = (ROOT / ".github" / "workflows" / "mesh.yml").read_text(encoding="utf-8")
        self.assertIn("display.show_reasoning false", text)

    def test_dead_free_models_are_skipped(self):
        """তালিকায় থাকলেও মৃত মডেল ("Model unavailable") ব্যবহার হবে না।"""
        from mesh.models import discover_usable

        alive = {"a/model:free", "c/model:free"}
        picked = discover_usable(
            limit=2,
            tries=5,
            fetcher=lambda timeout=30: [
                {"id": "a/model:free", "pricing": {"prompt": "0", "completion": "0"},
                 "supported_parameters": ["tools"], "context_length": 200_000},
                {"id": "b/model:free", "pricing": {"prompt": "0", "completion": "0"},
                 "supported_parameters": ["tools"], "context_length": 190_000},
                {"id": "c/model:free", "pricing": {"prompt": "0", "completion": "0"},
                 "supported_parameters": ["tools"], "context_length": 180_000},
            ],
            checker=lambda m: m in alive,
        )
        self.assertEqual(picked, ["a/model:free", "c/model:free"])

    def test_verified_model_list_passes_key_to_workflow(self):
        text = (ROOT / ".github" / "workflows" / "mesh.yml").read_text(encoding="utf-8")
        block = text.split("Pick free models")[1].split("- name:")[0]
        self.assertIn("OPENROUTER_API_KEY", block)

    def test_model_unavailable_triggers_fallback(self):
        from mesh.textutil import looks_like_quota_problem

        self.assertTrue(looks_like_quota_problem("Error: Model unavailable: x/y:free"))

    def test_tool_call_junk_is_not_an_answer(self):
        from mesh.textutil import clean_reply

        junk = "<tool_call>read<param_key>filePath</param_key><param_value>/a</param_value></tool_call>"
        self.assertEqual(clean_reply(junk), "")
        self.assertEqual(clean_reply("আসল উত্তর " + junk), "আসল উত্তর")

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
        # key আছে — OpenHands এখন সক্রিয় (কিন্তু গ্রুপ চ্যাটে নয়)
        self.assertIn("openhands", active)
        self.assertNotIn("openhands", [a.name for a in config.chat_agents()])


class DoctorHonestyTest(unittest.TestCase):
    def test_disabled_agents_do_not_block(self):
        from mesh.doctor import run_doctor

        checks = run_doctor(
            MeshConfig.load(),
            environ={"GH_TOKEN": "x", "OPENROUTER_API_KEY": "sk-or-test", "OPENHANDS_API_KEY": "oh-test"},
            which=lambda n: "/bin/" + n,
            store_path=Path(tempfile.mkdtemp()) / "t.jsonl",
        )
        # key দেওয়া আছে → কোনো ব্যর্থতা নেই; বন্ধ এজেন্ট শুধু সতর্কতা
        fails = [c.item for c in checks if c.status == "fail"]
        self.assertEqual(fails, [])
        by_item = {c.item: c for c in checks}
        # OpenHands এখন চালু; key/env অনুযায়ী হয় ok, নাহয় warn (fail নয়)
        self.assertIn(by_item["🖐️ OpenHands"].status, ("ok", "warn"))


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

    def test_unclosed_reasoning_box_still_gives_an_answer(self):
        """বক্স বন্ধ না হলে আগে পুরো উত্তর হারিয়ে যেত — এখন কাঁচা লেখা ফেরত আসে।"""
        from mesh.textutil import clean_reply

        raw = (
            "⚠ tirith security scanner enabled but not available\n"
            "┌─ Reasoning ───────────┐\n"
            "আমি ঠিক আছি, কাজ করছি।\n"
        )
        self.assertEqual(clean_reply(raw), "┌─ Reasoning ───────────┐\nআমি ঠিক আছি, কাজ করছি।")

    def test_empty_output_only_when_truly_empty(self):
        from mesh.textutil import clean_reply

        self.assertEqual(clean_reply("   \n\n"), "")

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

    def test_cli_reports_when_no_free_model(self):
        """নেটওয়ার্ক থাকুক বা না থাকুক — টেস্টটা যেন নির্ভরযোগ্য হয়।"""
        from unittest import mock
        from mesh import cli
        from mesh import models

        with mock.patch.object(models, "discover", return_value=None):
            self.assertEqual(cli.main(["--free-model"]), 1)

    def test_cli_prints_discovered_model(self):
        from unittest import mock
        from mesh import cli
        from mesh import models

        with mock.patch.object(models, "discover", return_value="some/model:free"), mock.patch(
            "builtins.print"
        ) as fake_print:
            self.assertEqual(cli.main(["--free-model"]), 0)
            fake_print.assert_called_with("some/model:free")


class WorkflowShellHygieneTest(unittest.TestCase):
    """bash এ ভুল escape (tr '\\n') দিয়ে মডেলের নাম নষ্ট হয়েছিল — আর যেন না হয়।"""

    def test_no_literal_double_backslash_n_in_tr(self):
        text = (ROOT / ".github" / "workflows" / "mesh.yml").read_text(encoding="utf-8")
        self.assertNotIn("tr '\\\\n'", text)
        self.assertNotIn("tr '\\n'", text)

    def test_free_model_file_is_ignored(self):
        self.assertIn("free-model.txt", (ROOT / ".gitignore").read_text(encoding="utf-8"))


class NetworkIndependenceTest(unittest.TestCase):
    """নেটওয়ার্ক আছে বা নেই — টেস্ট সবসময় একই ফল দেবে।"""

    def test_free_model_list_is_mocked(self):
        from unittest import mock
        from mesh import cli, models

        with mock.patch.object(models, "discover_usable", return_value=["a/x:free", "b/y:free"]), mock.patch(
            "builtins.print"
        ) as fake_print:
            self.assertEqual(cli.main(["--free-model-list", "2"]), 0)
            fake_print.assert_called_with("a/x:free\nb/y:free")

    def test_free_model_list_empty_is_failure(self):
        from unittest import mock
        from mesh import cli, models

        with mock.patch.object(models, "discover_usable", return_value=[]):
            self.assertEqual(cli.main(["--free-model-list", "3"]), 1)


class EmptyReplyDiagnosticsTest(unittest.TestCase):
    def test_stderr_is_shown_when_reply_is_empty(self):
        spec = AgentSpec(name="hermes", command=["hermes", "chat", "-q", "{message}"])
        adapter = CliAdapter(spec, runner=lambda c, e, w, t: (0, "", "warning: model not loaded"))
        reply = adapter.send("হাই")
        self.assertFalse(reply.ok)
        self.assertIn("model not loaded", reply.text)


class OpenHandsCloudTest(unittest.TestCase):
    def test_reports_missing_key(self):
        from mesh.openhands_cloud import ask

        result = ask("হাই", api_key="")
        self.assertFalse(result.ok)
        self.assertIn("OPENHANDS_API_KEY", result.text)
        self.assertEqual(result.detail, "no-key")

    def test_uses_injected_sdk(self):
        from mesh.openhands_cloud import ask

        def factory(key, url, model):
            self.assertEqual(key, "oh-test")
            self.assertEqual(url, "https://app.all-hands.dev")

            def run(message):
                return f"ওদের ক্লাউড বলছে: {message}"

            return run

        result = ask("কাজ করো", api_key="oh-test", sdk_factory=factory)
        self.assertTrue(result.ok)
        self.assertIn("কাজ করো", result.text)

    def test_sdk_error_is_reported_plainly(self):
        from mesh.openhands_cloud import ask

        def factory(*_args):
            raise RuntimeError("401 Unauthorized")

        result = ask("হাই", api_key="k", sdk_factory=factory)
        self.assertFalse(result.ok)
        self.assertIn("401 Unauthorized", result.text)
        self.assertEqual(result.detail, "error")

    def test_empty_answer_is_failure(self):
        from mesh.openhands_cloud import ask

        result = ask("হাই", api_key="k", sdk_factory=lambda *a: (lambda m: "   "))
        self.assertFalse(result.ok)
        self.assertEqual(result.detail, "empty")

    def test_answer_is_read_from_state_events(self):
        """SDK-র RemoteConversation থেকে আসল উত্তর বের করা (object repr নয়)।"""
        from types import SimpleNamespace as NS

        from mesh.openhands_cloud import _last_text

        events = [
            NS(source="user", llm_message=NS(content=[NS(text="প্রশ্ন")])),
            NS(source="agent", llm_message=NS(content=[NS(text="হ্যাঁ, কাজ করছি")])),
        ]
        self.assertEqual(_last_text(NS(state=NS(events=events))), "হ্যাঁ, কাজ করছি")
        self.assertEqual(_last_text(NS(_state=NS(events=events))), "হ্যাঁ, কাজ করছি")

    def test_no_answer_is_empty_not_object_repr(self):
        from mesh.openhands_cloud import _last_text

        self.assertEqual(_last_text(object()), "")

    def test_only_team_allowed_models_are_used(self):
        """ওদের টিমে শুধু deepseek-*-flash চলে — plus দিলে 'not allowed to access model'।"""
        from mesh.openhands_cloud import DEFAULT_MODEL, MODEL_CANDIDATES

        self.assertNotIn("plus", DEFAULT_MODEL)
        self.assertIn(DEFAULT_MODEL, MODEL_CANDIDATES)

    def test_denied_model_falls_back_to_next_one(self):
        from mesh.openhands_cloud import ask

        tried = []

        def factory(key, url, model):
            tried.append(model)

            def run(message):
                if "plus" in model:
                    raise RuntimeError(
                        "team not allowed to access model. This team can only access models=['deepseek-v4.1-flash']"
                    )
                return "ঠিক আছি"

            return run

        result = ask("হাই", api_key="k", sdk_factory=factory, model="openhands/deepseek-v4.1-plus")
        self.assertTrue(result.ok)
        self.assertEqual(result.text, "ঠিক আছি")
        self.assertGreaterEqual(len(tried), 2)


class KeyStateTest(unittest.TestCase):
    def _state(self, tmp=None):
        from mesh.keystate import KeyState

        now = {"t": 1_000.0}
        state = KeyState(Path(tmp or tempfile.mkdtemp()) / "keystate.json", now=lambda: now["t"])
        return state, now

    def test_failed_key_goes_to_back_and_recovers(self):
        state, now = self._state()
        keys = [("OPENROUTER_API_KEY", "a"), ("OPENROUTER_API_KEY_2", "b")]
        state.mark_failed("OPENROUTER_API_KEY", seconds=600)
        ordered = state.order(keys)
        self.assertEqual(ordered[0][0], "OPENROUTER_API_KEY_2")
        self.assertTrue(state.is_cooling("OPENROUTER_API_KEY"))
        now["t"] += 601
        self.assertFalse(state.is_cooling("OPENROUTER_API_KEY"))
        self.assertEqual(state.order(keys)[0][0], "OPENROUTER_API_KEY")

    def test_success_clears_cooldown(self):
        state, _now = self._state()
        state.mark_failed("OPENROUTER_API_KEY", seconds=600)
        state.mark_ok("OPENROUTER_API_KEY")
        self.assertFalse(state.is_cooling("OPENROUTER_API_KEY"))

    def test_quota_error_marks_key_in_rotation(self):
        state, _now = self._state()
        spec = AgentSpec(name="claude", command=["claude", "-p", "{message}"], keys=["OPENROUTER_API_KEY"])

        def runner(cmd, env, cwd, timeout):
            return 1, "", "429 rate limit exceeded"

        from mesh.adapters import CliAdapter

        CliAdapter(spec, runner=runner, keystate=state, environ={"OPENROUTER_API_KEY": "k"}).send("হাই")
        self.assertTrue(state.is_cooling("OPENROUTER_API_KEY"))

    def test_success_does_not_mark(self):
        state, _now = self._state()
        spec = AgentSpec(name="claude", command=["claude", "-p", "{message}"], keys=["OPENROUTER_API_KEY"])
        from mesh.adapters import CliAdapter

        CliAdapter(
            spec, runner=lambda c, e, w, t: (0, "ঠিক আছে", ""),
            keystate=state, environ={"OPENROUTER_API_KEY": "k"},
        ).send("হাই")
        self.assertFalse(state.is_cooling("OPENROUTER_API_KEY"))


class PriorityTest(unittest.TestCase):
    def test_openhands_has_highest_priority(self):
        config = MeshConfig.load()
        priorities = {a.name: a.priority for a in config.agents}
        self.assertEqual(min(priorities, key=priorities.get), "openhands")
        self.assertLess(priorities["openhands"], priorities["claude"])

    def test_claude_ranks_last_among_workers(self):
        config = MeshConfig.load()
        priorities = {a.name: a.priority for a in config.agents}
        self.assertGreater(priorities["claude"], priorities["opencode"])
        self.assertGreater(priorities["claude"], priorities["hermes"])

    def test_router_prefers_higher_priority_on_tie(self):
        router = make_router()
        # কোনো কীওয়ার্ড বা mention নেই → ডিফল্ট; কিন্তু স্কোর সমান হলে priority আগে
        self.assertEqual(router.classify("হাই"), [router.config.settings.default_agent])


class OpenHandsAdapterTest(unittest.TestCase):
    def test_dry_run_does_not_call_cloud(self):
        from mesh.adapters import build_adapter

        spec = MeshConfig.load().get("openhands")
        adapter = build_adapter(spec, dry_run=True)
        reply = adapter.send("হাই")
        self.assertTrue(reply.ok)
        self.assertIn("[dry-run]", reply.text)

    def test_missing_key_gives_clear_message(self):
        from mesh.adapters import build_adapter

        spec = MeshConfig.load().get("openhands")
        reply = build_adapter(spec, environ={}).send("হাই")
        self.assertFalse(reply.ok)
        self.assertIn("OPENHANDS_API_KEY", reply.text)


class KeyCheckTest(unittest.TestCase):
    def _opener(self, responses):
        calls = []

        def opener(url, headers):
            calls.append((url, dict(headers)))
            for needle, resp in responses.items():
                if needle in url:
                    return resp
            return 404, ""

        opener.calls = calls
        return opener

    def test_valid_openrouter_key(self):
        from mesh.keycheck import check_key

        opener = self._opener({"openrouter.ai": (200, '{"data":{"label":"sk-or-...","usage":1.5,"limit":10,"is_free_tier":true}}')})
        result = check_key("OPENROUTER_API_KEY", "sk-or-secret", opener=opener)
        self.assertEqual(result.status, "ok")
        self.assertIn("free_tier=True", result.detail)
        self.assertNotIn("sk-or-secret", result.detail)

    def test_invalid_key_is_bad(self):
        from mesh.keycheck import check_key

        result = check_key("OPENROUTER_API_KEY", "bad", opener=self._opener({"openrouter.ai": (401, "")}))
        self.assertEqual(result.status, "bad")

    def test_quota_is_warning_not_bad(self):
        from mesh.keycheck import check_key

        result = check_key("GROQ_API_KEY", "g", opener=self._opener({"groq.com": (429, "")}))
        self.assertEqual(result.status, "warn")

    def test_gemini_uses_query_param(self):
        from mesh.keycheck import check_key

        opener = self._opener({"generativelanguage": (200, '{"models":[1,2,3]}')})
        result = check_key("GEMINI_API_KEY", "AIza-test", opener=opener)
        self.assertEqual(result.status, "ok")
        self.assertIn("models=3", result.detail)
        self.assertIn("?key=", opener.calls[0][0])

    def test_missing_key(self):
        from mesh.keycheck import check_key

        self.assertEqual(check_key("GEMINI_API_KEY", "", opener=self._opener({})).status, "bad")

    def test_manual_and_out_of_scope(self):
        from mesh.keycheck import check_key

        self.assertEqual(check_key("OPENHANDS_API_KEY", "x", opener=self._opener({})).status, "manual")
        self.assertEqual(check_key("CARTESIA_API_KEY", "x", opener=self._opener({})).status, "warn")

    def test_rotated_keys_are_checked(self):
        from mesh.keycheck import check_all

        opener = self._opener({"openrouter.ai": (200, '{"data":{"label":"x"}}')})
        results = check_all({"OPENROUTER_API_KEY": "a", "OPENROUTER_API_KEY_2": "b"}, opener=opener)
        names = [r.name for r in results]
        self.assertIn("OPENROUTER_API_KEY", names)
        self.assertIn("OPENROUTER_API_KEY_2", names)

    def test_table_never_leaks_values(self):
        from mesh.keycheck import check_all, to_text

        opener = self._opener({"openrouter.ai": (200, '{"data":{}}')})
        text = to_text(check_all({"OPENROUTER_API_KEY": "sk-or-VERYSECRET123"}, opener=opener))
        self.assertNotIn("VERYSECRET", text)
        self.assertIn("OPENROUTER_API_KEY", text)


class KeyCheckFixesTest(unittest.TestCase):
    def test_rotated_key_uses_base_probe(self):
        from mesh.keycheck import check_key

        def opener(url, headers):
            self.assertIn("Authorization", headers)
            return 200, '{"data":{"label":"x","free_tier":true}}'

        result = check_key("OPENROUTER_API_KEY_2", "sk-or-second", opener=opener)
        self.assertEqual(result.status, "ok")

    def test_user_agent_is_sent(self):
        from mesh.keycheck import check_key

        seen = {}

        def opener(url, headers):
            seen.update(headers)
            return 200, "{}"

        check_key("GROQ_API_KEY", "g", opener=opener)
        self.assertIn("User-Agent", seen)

    def test_vercel_typo_alias_supported(self):
        from mesh.keycheck import PROBES

        self.assertIn("VERCEL_AI_GETAWAY", PROBES)
        self.assertIn("VERCEL_AI_GATEWAY", PROBES)

    def test_base_name(self):
        from mesh.keycheck import base_name

        self.assertEqual(base_name("OPENROUTER_API_KEY_2"), "OPENROUTER_API_KEY")
        self.assertEqual(base_name("GEMINI_API_KEY"), "GEMINI_API_KEY")


class HermesProviderTest(unittest.TestCase):
    def test_all_hermes_commands_use_openrouter(self):
        agent = MeshConfig.load().get("hermes")
        for cmd in [agent.command, *agent.fallback_commands]:
            self.assertIn("openrouter", cmd, "শুধু openrouter provider ব্যবহার করতে হবে")
            self.assertNotIn("opencode", cmd)
