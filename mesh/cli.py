"""কমান্ড লাইন থেকে মেশ চালানো।

    python -m mesh.cli "হাই" --mode group
    python -m mesh.cli "টেস্ট ঠিক করো" --mode direct
    python -m mesh.cli "হাই" --mode group --dry-run      # কিছু চালাবে না, শুধু দেখাবে
    python -m mesh.cli --list
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from .adapters import Reply, subprocess_runner
from .chat import default_store
from .config import MeshConfig
from .router import Router


def _print_list(config: MeshConfig) -> None:
    print("\n🧩 টিমের তালিকা\n")
    for spec in config.agents:
        flag = "✅" if spec.enabled else "⛔"
        roles = ", ".join(spec.roles)
        keys = ", ".join(spec.keys) or "key লাগে না"
        print(f" {flag} {spec.display():<18} kind={spec.kind:<12} roles={roles}")
        print(f"    key: {keys}")
        if spec.notes:
            print(f"    টীকা: {spec.notes}")
    print()


def _print_replies(replies: list[Reply]) -> None:
    if not replies:
        print("⚠️ কোনো এজেন্টকে ডাকা হয়নি (সীমা শেষ বা তালিকা খালি)।")
        return
    for reply in replies:
        mark = "✅" if reply.ok else "❌"
        print(f"\n{mark} {reply.label}\n{'-' * 40}")
        print(reply.text.strip() or "(খালি উত্তর)")


def _post_as_comments(issue: int, replies: list[Reply], dry_run: bool) -> None:
    for reply in replies:
        if not reply.ok:
            continue
        body = f"**{reply.label}**\n\n{reply.text.strip()}"
        cmd = ["gh", "issue", "comment", str(issue), "--body", body]
        if dry_run:
            print(f"[dry-run] {' '.join(cmd[:4])} ...")
            continue
        code, out, err = subprocess_runner(cmd, dict(os.environ), ".", 120)
        print(("✅ comment যোগ হয়েছে" if code == 0 else f"❌ comment ব্যর্থ: {err.strip()[:200]}"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mesh", description="agent-mesh-router")
    parser.add_argument("message", nargs="?", default="", help="যে কথাটা এজেন্টদের বলতে চান")
    parser.add_argument("--mode", choices=["direct", "group"], default="direct")
    parser.add_argument("--issue", type=int, default=None, help="এই Issue-কে গ্রুপ চ্যাট বানাও")
    parser.add_argument("--dry-run", action="store_true", help="কিছু চালাবে না, শুধু দেখাবে")
    parser.add_argument("--json", action="store_true", help="মেশিন-পাঠ্য আউটপুট")
    parser.add_argument("--config", default=None)
    parser.add_argument("--list", action="store_true", help="টিমের তালিকা দেখাও")
    args = parser.parse_args(argv)

    config = MeshConfig.load(args.config)

    if args.list:
        _print_list(config)
        return 0

    if not args.message.strip():
        parser.error("একটা কথা লিখুন, যেমন: python -m mesh.cli \"হাই\" --mode group")

    router = Router(
        config,
        dry_run=args.dry_run,
        issue=args.issue,
        store=default_store(),
        log=None if args.json else (lambda msg: print(msg, file=sys.stderr)),
    )

    replies = router.group(args.message) if args.mode == "group" else router.direct(args.message)

    if args.issue:
        _post_as_comments(args.issue, replies, args.dry_run)

    if args.json:
        print(json.dumps([r.__dict__ for r in replies], ensure_ascii=False, indent=2))
    else:
        _print_replies(replies)
        print(f"\n📊 মোট কল: {router.calls} / {config.settings.max_calls_per_run}")

    return 0 if any(r.ok for r in replies) else 1


if __name__ == "__main__":
    raise SystemExit(main())
