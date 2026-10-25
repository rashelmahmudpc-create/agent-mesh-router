"""🩺 ডক্টর — এক নজরে দেখুন সব ঠিক আছে কি না।

    python3 -m mesh.cli --doctor
    python3 -m mesh.cli --doctor --json

কোনো এজেন্ট ইনস্টল নেই? কোনো key নেই? — সব একসাথে দেখা যাবে।
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from .chat import default_store
from .config import MeshConfig
from .keys import collect_keys

OK, WARN, FAIL = "ok", "warn", "fail"
ICON = {OK: "✅", WARN: "⚠️", FAIL: "❌"}


@dataclass
class Check:
    item: str
    status: str
    detail: str


def _mask(value: str) -> str:
    return value[:4] + "…" + value[-2:] if len(value) > 8 else "…"


def run_doctor(
    config: MeshConfig,
    environ: dict[str, str] | None = None,
    which=shutil.which,
    store_path: str | Path | None = None,
) -> list[Check]:
    env = environ if environ is not None else os.environ
    checks: list[Check] = []

    # ১) পাইথন ও কনফিগ
    py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    checks.append(Check("python", OK if sys.version_info >= (3, 9) else FAIL, py))

    names = [a.name.lower() for a in config.agents]
    dupes = {n for n in names if names.count(n) > 1}
    checks.append(
        Check("config/agents.json", FAIL if dupes else OK, f"{len(config.agents)} এজেন্ট" + (f", পুনরাবৃত্তি: {dupes}" if dupes else ""))
    )
    if not config.enabled():
        checks.append(Check("enabled agents", FAIL, "কোনো এজেন্ট চালু নেই"))

    # ২) প্রতিটা এজেন্ট
    for spec in config.agents:
        if not spec.enabled:
            checks.append(Check(spec.display(), WARN, "বন্ধ আছে (enabled=false)"))
            continue

        if spec.kind == "cli":
            binary = (spec.command[0] if spec.command else "")
            path = which(binary) if binary else None
            if path:
                checks.append(Check(spec.display(), OK, f"{binary} → {path}"))
            else:
                checks.append(
                    Check(spec.display(), WARN, f"{binary} ইনস্টল নেই (চালাতে `{binary}` লাগবে)")
                )
        elif spec.kind == "github_issue":
            has_gh = bool(which("gh"))
            has_token = bool(env.get("GH_TOKEN") or env.get("GITHUB_TOKEN"))
            if has_gh and has_token:
                checks.append(Check(spec.display(), OK, "gh + token ঠিক আছে"))
            else:
                missing = []
                if not has_gh:
                    missing.append("gh CLI")
                if not has_token:
                    missing.append("GH_TOKEN")
                checks.append(Check(spec.display(), WARN, "নেই: " + ", ".join(missing)))
        else:
            checks.append(Check(spec.display(), WARN, f"অজানা ধরন: {spec.kind}"))

        # key যাচাই
        if spec.keys:
            found = collect_keys(spec.keys, env)
            if found:
                shown = ", ".join(f"{var}={_mask(val)}" for var, val in found)
                checks.append(Check(f"{spec.name} keys", OK, f"{len(found)}টা পাওয়া গেছে ({shown})"))
            else:
                checks.append(Check(f"{spec.name} keys", FAIL, f"{', '.join(spec.keys)} কোথাও নেই"))
        else:
            checks.append(Check(f"{spec.name} keys", OK, "key লাগে না"))

    # ৩) চ্যাটের লগ লেখা যায় কি?
    store = default_store() if store_path is None else type(default_store())(store_path)
    try:
        store.append({"agent": "doctor", "text": "health check"})
        checks.append(Check("store", OK, str(store.path)))
    except OSError as exc:
        checks.append(Check("store", FAIL, f"লেখা যাচ্ছে না: {exc}"))

    return checks


def print_checks(checks: list[Check]) -> int:
    print("\n🩺 মেশ ডক্টর\n" + "=" * 46)
    for c in checks:
        print(f" {ICON.get(c.status, '•')} {c.item:<22} {c.detail}")
    fails = sum(1 for c in checks if c.status == FAIL)
    warns = sum(1 for c in checks if c.status == WARN)
    print("=" * 46)
    verdict = "সব ঠিক ✅" if not fails else f"{fails}টা সমস্যা ❌"
    print(f" ফল: {verdict}" + (f"  ({warns}টা সতর্কতা ⚠️)" if warns else "") + "\n")
    return 0 if not fails else 1


def main(json_out: bool = False, config: MeshConfig | None = None) -> int:
    checks = run_doctor(config or MeshConfig.load())
    if json_out:
        print(json.dumps([asdict(c) for c in checks], ensure_ascii=False, indent=2))
        return 0 if all(c.status != FAIL for c in checks) else 1
    return print_checks(checks)
