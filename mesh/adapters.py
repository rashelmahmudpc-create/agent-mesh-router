"""এজেন্টের সাথে কথা বলার সেতু (adapter)।

দুই রকম সেতু আছে:
  1) cli          — opencode / cline / claude / hermes কে কমান্ড দিয়ে চালানো
  2) github_issue — OpenHands (ওদের ক্লাউড) কে GitHub Issue দিয়ে কাজ দেওয়া
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Callable

from .config import AgentSpec
from .keystate import KeyState, default_state
from .keys import collect_keys, expand_env_value
from .textutil import clean_reply, clip, looks_like_quota_problem, strip_ansi

# runner(cmd, env, cwd, timeout) -> (exit_code, stdout, stderr)
Runner = Callable[[list[str], dict[str, str], str, int], tuple[int, str, str]]


def subprocess_runner(cmd: list[str], env: dict[str, str], cwd: str, timeout: int) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, env=env, timeout=timeout, text=True, capture_output=True, check=False
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except FileNotFoundError as exc:
        return 127, "", f"কমান্ড পাওয়া যায়নি: {exc}"
    except subprocess.TimeoutExpired:
        return 124, "", f"সময় শেষ ({timeout}s)"


@dataclass
class Reply:
    agent: str
    label: str
    ok: bool
    text: str
    meta: dict = field(default_factory=dict)


class CliAdapter:
    """টার্মিনালে চলা এজেন্ট (OpenCode, Cline, Claude Code, Hermes)।"""

    def __init__(
        self,
        spec: AgentSpec,
        runner: Runner | None = None,
        workdir: str = ".",
        dry_run: bool = False,
        environ: dict[str, str] | None = None,
        reply_limit: int = 4000,
        keystate: KeyState | None = None,
    ) -> None:
        self.spec = spec
        self.runner = runner or subprocess_runner
        self.workdir = workdir
        self.dry_run = dry_run
        self.environ = environ if environ is not None else dict(os.environ)
        self.reply_limit = reply_limit
        self.keystate = keystate or default_state()

    def _cmd(self, message: str, template: list[str] | None = None) -> list[str]:
        out = []
        for part in (template or self.spec.command):
            part = expand_env_value(part, self.environ) if part.startswith("$") else part
            out.append(part.replace("{message}", message).replace("{workdir}", self.workdir))
        return out

    def _base_env(self) -> dict[str, str]:
        env = dict(self.environ)
        for name, value in self.spec.env.items():
            resolved = expand_env_value(value, self.environ)
            # "$VAR" দিয়ে দেওয়া আর VAR নেই → সেট করব না (খালি মান বিভ্রান্তি তৈরি করে)
            if not resolved and (value or "").startswith("$"):
                continue
            env[name] = resolved
        return env

    def send(self, message: str, sender: str = "owner") -> Reply:
        """প্রথম কমান্ড; ব্যর্থ হলে (কোটা/লিমিট) fallback কমান্ডগুলো চেষ্টা করে।"""
        templates = [self.spec.command, *self.spec.fallback_commands]
        attempts = self.keystate.order(collect_keys(self.spec.keys, self.environ)) or [("", "")]

        last = Reply(self.spec.name, self.spec.display(), False, "কোনো চেষ্টা হয়নি")
        for template in templates:
            if not template:
                continue
            cmd = self._cmd(message, template)
            for var, value in attempts:
                env = self._base_env()
                if var:
                    env[re.sub(r"_\d+$", "", var)] = value
                if self.dry_run:
                    return Reply(
                        self.spec.name, self.spec.display(), True,
                        f"[dry-run] {' '.join(cmd)}", {"dry_run": True},
                    )
                code, out, err = self.runner(cmd, env, self.workdir, self.spec.timeout_sec)
                text = strip_ansi(out or err)
                cleaned = clean_reply(out or "")
                if code == 0 and cleaned:
                    if var:
                        self.keystate.mark_ok(var)
                    reply_text = clip(cleaned, self.reply_limit)
                    return Reply(self.spec.name, self.spec.display(), True, reply_text, {"key": var or None})
                if code == 0:
                    hint = clip(strip_ansi(err or ""), 800)
                    last = Reply(
                        self.spec.name, self.spec.display(), False,
                        "❌ এজেন্ট চালু হলো কিন্তু কোনো উত্তর দিল না (খালি আউটপুট)।"
                        + (f"\n\n_জানানো হয়েছে:_ {hint}" if hint else ""),
                        {"code": code, "empty": True},
                    )
                    break  # এই কমান্ডে উত্তর নেই — পরের (fallback) চেষ্টা করি
                last = Reply(self.spec.name, self.spec.display(), False, clip(text, self.reply_limit), {"code": code})
                if not looks_like_quota_problem(out, err):
                    return last  # key বা কোটা সমস্যা নয় — fallback দিয়ে লাভ নেই
                if var:
                    # এই key কিছুক্ষণ বন্ধ রাখি, পরের রানে যেন সময় নষ্ট না হয়
                    self.keystate.mark_failed(var, reason=clip(text, 160))
        return last


class GitHubIssueAdapter:
    """OpenHands কে GitHub Issue ভরে কাজ দেওয়া (উত্তর আসে পরে, comment হিসেবে)।"""

    def __init__(
        self,
        spec: AgentSpec,
        runner: Runner | None = None,
        workdir: str = ".",
        dry_run: bool = False,
        issue: int | None = None,
        environ: dict[str, str] | None = None,
    ) -> None:
        self.spec = spec
        self.runner = runner or subprocess_runner
        self.workdir = workdir
        self.dry_run = dry_run
        self.issue = issue
        self.environ = environ if environ is not None else dict(os.environ)

    def send(self, message: str, sender: str = "owner") -> Reply:
        mention = self.spec.mention or f"@{self.spec.name}"
        body = f"{mention} {message}\n\n_from: {sender}_"
        if self.issue:
            cmd = ["gh", "issue", "comment", str(self.issue), "--body", body]
        else:
            title = clip(message, 60).replace("\n", " ") or "agent-mesh task"
            cmd = ["gh", "issue", "create", "--title", f"🖐️ {title}", "--body", body]
        if self.dry_run:
            return Reply(self.spec.name, self.spec.display(), True, f"[dry-run] {' '.join(cmd)}", {"dry_run": True})

        code, out, err = self.runner(cmd, dict(self.environ), self.workdir, 120)
        if code == 0:
            return Reply(
                self.spec.name,
                self.spec.display(),
                True,
                f"কাজ পাঠানো হয়েছে (উত্তর comment হিসেবে আসবে): {out.strip()}",
                {"async": True},
            )
        return Reply(self.spec.name, self.spec.display(), False, clip(err or out, 1500), {"code": code})


class OpenHandsCloudAdapter:
    """🖐️ OpenHands — ওদের ক্লাউড API (SDK), প্রতিটা কাজ আলাদা conversation এ।"""

    def __init__(self, spec, dry_run: bool = False, environ: dict | None = None, reply_limit: int = 4000):
        self.spec = spec
        self.dry_run = dry_run
        self.environ = environ if environ is not None else dict(os.environ)
        self.reply_limit = reply_limit

    def send(self, message: str, sender: str = "owner") -> Reply:
        if self.dry_run:
            return Reply(self.spec.name, self.spec.display(), True, f"[dry-run] openhands cloud ← {message}",
                         {"dry_run": True})
        from .openhands_cloud import ask

        result = ask(message, api_key=(self.environ.get("OPENHANDS_API_KEY") or "").strip())
        return Reply(
            self.spec.name,
            self.spec.display(),
            result.ok,
            clip(clean_reply(result.text), self.reply_limit),
            {"detail": result.detail},
        )


def build_adapter(
    spec: AgentSpec,
    runner: Runner | None = None,
    workdir: str = ".",
    dry_run: bool = False,
    issue: int | None = None,
    environ: dict[str, str] | None = None,
    reply_limit: int = 4000,
):
    if spec.kind == "openhands_cloud":
        return OpenHandsCloudAdapter(spec, dry_run=dry_run, environ=environ, reply_limit=reply_limit)
    if spec.kind == "github_issue":
        return GitHubIssueAdapter(spec, runner=runner, workdir=workdir, dry_run=dry_run, issue=issue, environ=environ)
    return CliAdapter(
        spec, runner=runner, workdir=workdir, dry_run=dry_run, environ=environ, reply_limit=reply_limit
    )
