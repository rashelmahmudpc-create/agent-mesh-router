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
import sys

from .adapters import Reply
from .chat import default_store
from .issue import fetch_hall, post_comment
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


def _probe(config: MeshConfig, dry_run: bool = False, strict: bool = False) -> int:
    """প্রতিটা এজেন্টকে এক লাইনের প্রশ্ন — কে সত্যিই সাড়া দেয় দেখা যায়।"""
    from concurrent.futures import ThreadPoolExecutor

    router = Router(config, dry_run=dry_run, store=default_store())
    targets = [spec.name for spec in config.enabled() if spec.has_role("chat")]
    prompt = "শুধু OK লিখুন, আর কিছু নয়।"

    with ThreadPoolExecutor(max_workers=min(8, max(1, len(targets)))) as pool:
        futures = {name: pool.submit(router.call, name, prompt) for name in targets}
        replies = [futures[name].result() for name in targets]

    print("\n🔎 প্রোব — কে সাড়া দিচ্ছে?\n" + "=" * 46)
    for reply in replies:
        mark = "✅" if reply.ok else "❌"
        brief = (reply.text or "").strip().splitlines()[0][:60] if reply.text else "(ফাঁকা)"
        print(f" {mark} {reply.label:<18} {brief}")
    print("=" * 46)
    good = sum(1 for r in replies if r.ok)
    print(f" সাড়া দিয়েছে: {good}/{len(replies)}\n")
    return (0 if good else 1) if strict else 0


def _print_replies(replies: list[Reply]) -> None:
    if not replies:
        print("⚠️ কোনো এজেন্টকে ডাকা হয়নি (সীমা শেষ বা তালিকা খালি)।")
        return
    for reply in replies:
        mark = "✅" if reply.ok else "❌"
        print(f"\n{mark} {reply.label}\n{'-' * 40}")
        print(reply.text.strip() or "(খালি উত্তর)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mesh", description="agent-mesh-router")
    parser.add_argument("message", nargs="?", default="", help="যে কথাটা এজেন্টদের বলতে চান")
    parser.add_argument("--mode", choices=["direct", "group"], default="direct")
    parser.add_argument("--issue", type=int, default=None, help="এই Issue-কে গ্রুপ চ্যাট বানাও")
    parser.add_argument("--dry-run", action="store_true", help="কিছু চালাবে না, শুধু দেখাবে")
    parser.add_argument("--json", action="store_true", help="মেশিন-পাঠ্য আউটপুট")
    parser.add_argument(
        "--strict", action="store_true", help="কেউ সাড়া না দিলে ব্যর্থ হিসেবে গণ্য করো (CI তে লাল হবে)"
    )
    parser.add_argument("--config", default=None)
    parser.add_argument("--list", action="store_true", help="টিমের তালিকা দেখাও")
    parser.add_argument("--doctor", action="store_true", help="সব ঠিক আছে কি না দেখাও")
    parser.add_argument("--probe", action="store_true", help="প্রতিটা এজেন্টকে একটা ছোট প্রশ্ন করে দেখো কে সাড়া দেয়")
    parser.add_argument(
        "--free-model", action="store_true", help="এখন কোন মডেল সত্যিই ফ্রি — OpenRouter তালিকা থেকে বলে দাও"
    )
    parser.add_argument(
        "--check-keys", action="store_true",
        help="🔑 কোন key সত্যিই কাজ করছে দেখাও (key কখনো ছাপা হয় না)",
    )
    parser.add_argument(
        "--openhands", metavar="TEXT", default=None,
        help="🖐️ OpenHands ক্লাউড API দিয়ে একবার কাজ চালাও (OPENHANDS_API_KEY লাগবে)",
    )
    parser.add_argument(
        "--free-model-list", type=int, default=0, metavar="N",
        help="সেরা N টা ফ্রি মডেলের আইডি (প্রতি লাইনে একটা)",
    )
    args = parser.parse_args(argv)

    config = MeshConfig.load(args.config)

    if args.doctor:
        from .doctor import main as doctor_main

        return doctor_main(json_out=args.json, config=config, strict=args.strict)

    if args.list:
        _print_list(config)
        return 0

    if args.check_keys:
        from .keycheck import check_all, to_json, to_text

        results = check_all(dict(os.environ))
        print(to_json(results) if args.json else to_text(results))
        return 0

    if args.openhands:
        from .openhands_cloud import ask

        result = ask(args.openhands)
        print(("✅ " if result.ok else "") + result.text)
        return 0 if result.ok else 1

    if args.free_model_list:
        from .models import discover_usable

        found = discover_usable(
            limit=args.free_model_list,
            api_key=(os.environ.get("OPENROUTER_API_KEY") or "").strip(),
        )
        if found:
            print("\n".join(found))
            return 0
        print("⚠️ ফ্রি মডেল পাওয়া যায়নি", file=sys.stderr)
        return 1

    if args.free_model:
        from .models import discover

        model = discover()
        if model:
            print(model)
            return 0
        print("⚠️ ফ্রি মডেল পাওয়া যায়নি (নেটওয়ার্ক বা তালিকা বদলেছে)", file=sys.stderr)
        return 1

    if args.probe:
        return _probe(config, dry_run=args.dry_run, strict=args.strict)

    if not args.message.strip():
        parser.error("একটা কথা লিখুন, যেমন: python -m mesh.cli \"হাই\" --mode group")

    # উত্তর তৈরি হওয়ামাত্রই Issue-এ comment যাবে → অ্যাপে দ্রুত দেখা যাবে
    posted_ids: set[int] = set()

    def _post_reply(reply) -> None:
        body = reply.text if reply.ok else f"❌ সাড়া দিতে পারিনি\n\n{reply.text}"
        if post_comment(args.issue, reply.agent, reply.label, body, dry_run=args.dry_run):
            posted_ids.add(id(reply))

    router = Router(
        config,
        dry_run=args.dry_run,
        issue=args.issue,
        store=default_store(),
        log=None if args.json else (lambda msg: print(msg, file=sys.stderr)),
        on_reply=_post_reply if args.issue else None,
    )

    history = fetch_hall(args.issue) if (args.issue and args.mode == "group") else ""
    if history and not args.json:
        print(f"🏛️ Issue #{args.issue} এর আগের আলোচনা পড়া হয়েছে ({len(history)} অক্ষর)", file=sys.stderr)

    replies = (
        router.group(args.message, history=history)
        if args.mode == "group"
        else router.direct(args.message)
    )

    if args.issue:
        # সফল ও ব্যর্থ — দুটোরই comment যায়, যাতে Issue দেখেই বোঝা যায় কী হলো
        # (on_reply আগেই যেগুলো পোস্ট করেছে, সেগুলো আবার নয়)
        for reply in replies:
            if id(reply) in posted_ids:
                continue
            _post_reply(reply)

    if args.json:
        print(json.dumps([r.__dict__ for r in replies], ensure_ascii=False, indent=2))
    else:
        _print_replies(replies)
        print(f"\n📊 মোট কল: {router.calls} / {config.settings.max_calls_per_run}")

    # কোনো এজেন্ট উত্তর না দিলেও রান সবুজ থাকবে — ফলাফল উপরে ছাপা হয়।
    # কঠোরভাবে ব্যর্থ করতে চাইলে --strict
    return (0 if any(r.ok for r in replies) else 1) if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
