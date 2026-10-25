# Handoff — 🎯 app picker: শুধু বাছা এজেন্টরা উত্তর দেবে (2026-10-25)

**PR:** 👉 https://github.com/rashelmahmudpc-create/agent-mesh-router/pull/64 (CI ✓, mergeable)
**Asked:** "সবাই কেনো উত্তর দিচ্ছে বুঝলাম না — drop-down থেকে যে এজেন্ট সিলেক্ট করবো শুধু সে উত্তর দিবে, মাল্টিপল করলে মাল্টিপল দিবে"
**Priority:** 3 (AI-agent infrastructure)
**Role:** worker

## কেন আগে সবাই উত্তর দিত

- Actions-এ মোড ছিল **group`ই** — অ্যাপের 👤 এজেন্ট ট্যাবেও (লগে `▶️ mode=group`), তাই ৪ জন × ৩ রাউন্ড।
- **এজেন্ট বাছার কোনো উপায়ই ছিল না** — অ্যাপে ছিল শুধু এজেন্ট/গ্রুপ টগল, আর `@mesh` মানেই সবাই।
- "শুধু Claude Code উত্তর দাও" লিখলেও সবাই উত্তর দিয়েছিল — কথাটা ছিল শুধু প্রম্পটের ভেতরে, রাউটারের কাছে নির্দেশ ছিল না।

## Done

- `docs/app/index.html`
  - Composer-এর উপরে **pickbar** (`#pickBtn` + `#agentPick`): "সবাই" অথবা এজেন্টদের টিক-লিস্ট।
    একজনে টিক = শুধু সে-ই, একাধিকে টিক = যাদের টিক দিয়েছেন সবাই (প্যানেল খোলা থাকে)।
  - `cfg.agents` (খালি = সবাই), label কিছু না বাছলে "সবাই", একজন হলে নাম, একাধিক হলে "২ জন"।
  - চারটা পথেই মানা: **worker (`netRun`)**, **GitHub সরাসরি (`ghRun`)**, **নিজের key (`fastRun`)**, **ডেমো (`demoGroup`)**।
  - মার্কার এখন: `<!-- app:<ts> mode:agent|group targets:hermes -->`; বাছা না থাকলে `targets:` যায় না।
  - সংস্করণ `2026-10-26.2`; API চুক্তিতে `agents:[…]` যোগ।
- `worker/index.js` — payload থেকে `agents` পড়ে (১) comment-এর মার্কারে `targets:` বসায়, (২) দ্রুত লেনে (`FAST`) শুধু বাছা persona-দের উত্তর দেয়।
- `mesh/textutil.py` — `app_targets_of()` (`targets:` মার্কার পড়ে)।
- `mesh/router.py` — `direct(only=…)` / `group(only=…)`: বাছা তালিকার বাইরের এজেন্ট ডাকা পড়ে না,
  এমনকি অন্য এজেন্ট `@mention` করলেও না (আগে হতো)।
- `mesh/cli.py` — মার্কার দেখে নিজেই মোড/বাছা ঠিক করে (workflow অপরিবর্তিত থাকলেও চলে); নতুন `--agents a,b`।
- `tests/`: `test_mesh.py` (`PickAgentsTest`, `CliPickTest`, `app_targets_of`), `worker_check.mjs` (drop-down), `dom_check.mjs` (পিকার UI + comment-এ `targets:`)
  — সাথে **পুরনো একটা টেস্ট বাগও ঠিক হলো** (দ্রুত মোডের পরীক্ষায় `server.json` কে LLM কল ধরা হচ্ছিল, তাই টেস্ট সবসময় লাল থাকত)।

## Verified

```
$ python3 -m unittest discover -s tests
Ran 187 tests in 10.766s
OK

$ node tests/js/worker_check.mjs
✔ 🎯 drop-down: বাছা একজনই উত্তর দেয় — Hermes
✔ 🎯 drop-down: দুইজন বাছলে দুইজনই — Claude Code,Hermes
✔ 🎯 drop-down: না বাছলে সবাই (৪ জন) — OpenCode,Claude Code,Hermes,OpenHands
✔ 🎯 ধীর লেন: মার্কারে targets:hermes যায়
✅ Worker সব পরীক্ষায় পাস

$ node tests/js/dom_check.mjs          (jsdom)
✔ 🎯 পিকার খোলে
✔ 🎯 একজন বাছলে label-এ তার নাম — ☤ Hermes
✔ 🎯 দুইজন বাছলে label-এ সংখ্যা — ২ জন
✔ 🎯 মার্কারে targets:hermes যায় — … <!-- app:1792952692593 mode:agent targets:hermes -->
✅ সব DOM পরীক্ষা পাস

$ python3 -m mesh.cli '@mesh আজ কী করবো?\n<!-- app:1 mode:agent targets:hermes -->' --mode group --issue 3 --dry-run
[dry-run] gh issue comment 3 ← ☤ Hermes
[dry-run] hermes chat -q আজ কী করবো?
📊 মোট কল: 1 / 8
```

## Still open

- **স্যারের কাজ:** PR **#64** মার্জ করে অ্যাপ রিফ্রেশ করুন → composer-এর উপরে "সবাই ▾" চিপ দেখবেন।
- merge + deploy এর পর সত্যিকারের একটা প্রশ্নে যাচাই করতে হবে।
- workflow-এর ছোট প্যাচ (`.github/workflows/mesh.yml`) তখনো **push করা হয়নি** — প্যাচটা
  `docs/handoffs/2026-10-25-app-relevance.md` এ আছে; দরকার নেই, `mesh/cli.py` নিজেই কাজটা করে।

## Do not touch

- `config/agents.json` এর `max_calls_per_run` / `max_rounds` / `max_pair_calls`।
- `FAST=off` (স্যারের সিদ্ধান্ত)।
- Issue #3 — ইতিহাস মুছবেন না।