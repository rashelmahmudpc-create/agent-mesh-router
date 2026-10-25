"""🧠 রাউটার — কে কোন কাজ করবে, সেটা ঠিক করে।

দুইটা মোড:
  * direct — ম্যানেজার কাজ ভাগ করে শুধু যার প্রযোজ্য তাকে ডাকে
  * group  — সবাই একসাথে উত্তর দেয়, কেউ কাউকে @mention করে ডাকতে পারে

বুদ্ধি খাটানোর নিয়ম (সস্তা থেকে দামি):
  ১) @mention দেখে চেনা            → ০ কল
  ২) কীওয়ার্ড মিলিয়ে চেনা          → ০ কল
  ৩) ডিফল্ট এজেন্ট                 → ০ কল
  (ভবিষ্যতে দরকার হলে এর পরে ছোট ফ্রি মডেল বসানো যাবে)
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable

from .adapters import Reply, build_adapter
from .chat import Store, default_store
from .config import AgentSpec, MeshConfig
from .textutil import clip, find_mentions

LogFn = Callable[[str], None]


class Router:
    def __init__(
        self,
        config: MeshConfig,
        runner=None,
        workdir: str = ".",
        dry_run: bool = False,
        issue: int | None = None,
        store: Store | None = None,
        environ: dict[str, str] | None = None,
        log: LogFn | None = None,
    ) -> None:
        self.config = config
        self.runner = runner
        self.workdir = workdir
        self.dry_run = dry_run
        self.issue = issue
        self.store = store or default_store()
        self.environ = environ
        self.log = log or (lambda _msg: None)

        self.calls = 0
        self.pair_calls: dict[tuple[str, str], int] = {}
        self.replies: list[Reply] = []

    # ---------- সীমা রক্ষা ----------

    def _can_call(self, name: str, sender: str = "owner") -> tuple[bool, str]:
        spec = self.config.get(name)
        if spec is None:
            return False, "এই নামে কোনো এজেন্ট নেই"
        if not spec.enabled:
            return False, "এজেন্ট বন্ধ আছে"
        if self.calls >= self.config.settings.max_calls_per_run:
            return False, "এই রানে কলের সীমা শেষ"
        if sender not in ("owner", name):
            used = self.pair_calls.get((sender, name), 0)
            if used >= self.config.settings.max_pair_calls:
                return False, f"{sender} ↔ {name} কথা বলার সীমা শেষ"
        if spec.daily_limit and self.store.today_count(name) >= spec.daily_limit:
            return False, "আজকের কোটা শেষ"
        return True, ""

    def _bump(self, name: str, sender: str = "owner") -> None:
        self.calls += 1
        if sender not in ("owner", name):
            key = (sender, name)
            self.pair_calls[key] = self.pair_calls.get(key, 0) + 1

    # ---------- একটা এজেন্টকে ডাকা ----------

    def call(self, name: str, message: str, sender: str = "owner") -> Reply:
        ok, reason = self._can_call(name, sender)
        spec = self.config.get(name)
        if not ok or spec is None:
            reply = Reply(name, name, False, f"⏭️ ডাকা হয়নি — {reason}")
            return reply

        self._bump(name, sender)
        adapter = build_adapter(
            spec,
            runner=self.runner,
            workdir=self.workdir,
            dry_run=self.dry_run,
            issue=self.issue,
            environ=self.environ,
            reply_limit=self.config.settings.reply_char_limit,
        )
        self.log(f"→ {spec.display()} কে পাঠানো হচ্ছে")
        reply = adapter.send(message, sender)
        self.store.append(
            {"mode": "call", "agent": name, "sender": sender, "ok": reply.ok, "text": reply.text[:2000]}
        )
        self.replies.append(reply)
        self.log(f"← {spec.display()} {'✅' if reply.ok else '❌'}")
        return reply

    # ---------- বোঝা: কাজটা কার? ----------

    def classify(self, message: str, exclude: Iterable[str] = ()) -> list[str]:
        exclude = {e.lower() for e in exclude}
        known = self.config.names()

        mentioned = [m for m in find_mentions(message, known) if m not in exclude]
        if mentioned:
            return mentioned[:2]

        low = (message or "").lower()
        scored: list[tuple[int, int, str]] = []
        ordered = sorted(self.config.enabled(), key=lambda a: (a.priority, a.name))
        for order, spec in enumerate(ordered):
            if spec.name.lower() in exclude:
                continue
            score = sum(1 for kw in spec.keywords if kw.lower() in low)
            if score:
                scored.append((score, -order, spec.name))
        if scored:
            return [max(scored)[2]]

        default = self.config.settings.default_agent
        spec = self.config.get(default)
        if spec and spec.enabled and default.lower() not in exclude:
            return [default]
        chat = self.config.chat_agents()
        if chat:
            return [chat[0].name]
        return []

    # ---------- মোড ১: ডাইরেক্ট ----------

    def direct(self, message: str) -> list[Reply]:
        out: list[Reply] = []
        for name in self.classify(message):
            reply = self.call(name, message, "owner")
            out.append(reply)
            if reply.ok:
                return out
        # ব্যাকআপ: প্রথমটা ব্যর্থ হলে অন্যদের চেষ্টা (সর্বোচ্চ ২টা)
        tried = {r.agent.lower() for r in out}
        for spec in self.config.chat_agents():
            if spec.name.lower() in tried:
                continue
            if len(out) >= 3:
                break
            reply = self.call(spec.name, message, "owner")
            out.append(reply)
            if reply.ok:
                break
        return out

    # ---------- মোড ২: গ্রুপ ----------

    def _dispatch(self, targets: list[tuple[str, str]], message: str) -> list[Reply]:
        """(এজেন্ট, কে ডাকছে) জোড়াগুলোকে একসাথে (parallel) ডাকে।"""
        runnable: list[tuple[str, str]] = []
        for name, sender in targets:
            if (name, sender) in runnable:
                continue
            if self._can_call(name, sender)[0]:
                runnable.append((name, sender))
        if not runnable:
            return []
        with ThreadPoolExecutor(max_workers=min(8, len(runnable))) as pool:
            futures = [pool.submit(self.call, name, message, sender) for name, sender in runnable]
            return [f.result() for f in futures]

    def group(self, message: str, history: str = "") -> list[Reply]:
        """সবাইকে ডাকা হয়; `history` হলে (Issue এর পুরনো কথা) সেটাও পড়ে।"""
        targets: list[tuple[str, str]] = [(spec.name, "owner") for spec in self.config.chat_agents()]
        known = self.config.names()
        collected: list[Reply] = []
        context = history.strip()

        for round_no in range(self.config.settings.max_rounds):
            if not targets:
                break
            if round_no == 0 and context:
                prompt = (
                    f"{message}\n\n[হলঘরে (Issue) আগে যা হয়েছে]\n{context}\n\n"
                    "উপরের আলোচনা পড়ে নিজের মত সংক্ষেপে উত্তর দাও।"
                )
            elif round_no == 0:
                prompt = message
            else:
                prompt = (
                    f"{message}\n\n[গ্রুপ চ্যাট পর্যন্ত যা হয়েছে]\n{context}\n\n"
                    "উপরের আলোচনা পড়ে নিজের মত সংক্ষেপে উত্তর দাও।"
                )
            self.log(f"— রাউন্ড {round_no + 1}: {', '.join(name for name, _ in targets)}")
            round_replies = self._dispatch(targets, prompt)
            if not round_replies:
                break
            collected.extend(round_replies)

            context = "\n".join(
                [context, *[f"- {r.label}: {clip(r.text, 400)}" for r in collected if r.ok]]
            ).strip()

            next_targets: list[tuple[str, str]] = []
            for reply in round_replies:
                for mention in find_mentions(reply.text, known):
                    if mention == reply.agent.lower():
                        continue
                    pair = (mention, reply.agent.lower())
                    if pair not in next_targets:
                        next_targets.append(pair)
            # প্রথম রাউন্ডের পর শুধু ডাকা এজেন্টেরাই উত্তর দেয়
            targets = next_targets

        return collected
