# Handoff — উত্তর দ্রুত দেখানো + লাইভ অবস্থা (2026-10-25)

**Asked:** মালিকের অভিযোগ — “এত কিছু বুঝি না; উত্তর আর লাইভ অবস্থা দেখা যাবে, আর ৩–৯ মিনিট দেরি কেন?”
**Priority:** 3
**Role:** worker

**Done:**
- `mesh/router.py` — নতুন `on_reply` callback: **যে এজেন্ট আগে শেষ করে, তার উত্তর সাথে সাথে** Issue-এ যায় (`_dispatch` এখন `as_completed` ব্যবহার করে)। callback ফেল করলেও রান থামে না।
- `mesh/cli.py` — `post_comment` এখন reply তৈরি হওয়ামাত্রই চলে; শেষে ডাবল-পোস্ট হয় না (`posted_ids`)
- ❌ `.github/workflows/mesh.yml`-এ CLI cache যোগ করা যায়নি: GitHub App (Cline)-এর `workflows`
  পারমিশন নেই, তাই push reject হয়। ওটা বাদ দেওয়া হলো — বাকি উন্নতি ওটার উপর নির্ভর করে না।
- `docs/app/index.html` — অপেক্ষা ১০ মিনিট, quiet-break ১২s → ২০s (দেরিতে আসা এজেন্টের উত্তরও ধরা পড়ে)
- `tests/test_mesh.py` — `StreamingReplyTest` (৩টা নতুন টেস্ট)
- `docs/pwa-bn.md` — “কত দ্রুত উত্তর আসে” অংশ

**Verified:**
```
$ python3 -m unittest discover -s tests
Ran 135 tests in 9.340s
OK

$ python3 -m mesh.cli "হাই সবাই" --issue 3 --mode group --dry-run | grep 'gh issue comment'
      1 [dry-run] gh issue comment 3 ← ☤ Hermes
      1 [dry-run] gh issue comment 3 ← 🟠 Claude Code
      1 [dry-run] gh issue comment 3 ← 🧑‍💻 OpenCode      ← প্রতিটা একবার, ডাবল নয়

$ node tests/js/dom_check.mjs
✅ সব DOM পরীক্ষা পাস (GitHub মোড সহ)
```

**Still open:**
- আসল গতি যাচাই করতে একটা নতুন `@mesh` মেসেজ দিয়ে রান-টাইম মাপা দরকার (প্রথম comment কত সেকেন্ডে আসে)। আগের রান: route step 397s, installs 71s।
- সবচেয়ে ধীর এজেন্ট কোনটা তা এখনো আলাদা করে মাপা হয়নি; দরকার হলে তার `timeout_sec` কমানো যাবে (`config/agents.json`)।

**Do not touch:**
- `max_calls_per_run` / `max_rounds` / `max_pair_calls` — ছোঁবেন না (AGENTS.md §13)।
- `on_reply` কে async/await বানাবেন না — Actions-এ সিঙ্ক্রোনাস `gh` কলই যথেষ্ট।
