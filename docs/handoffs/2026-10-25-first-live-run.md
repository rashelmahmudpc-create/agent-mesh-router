# Handoff — first live run, Claude works (2026-10-25)

**Asked:** Issue #3 এ `@mesh হাই সবাই` — সবাই নিজের পরিচয় দেবে।
**Priority:** 3 (developer skills and AI-agent infrastructure)
**Role:** worker

## ✅ যা প্রমাণিত হলো

- 🟠 **Claude Code সত্যিই কাজ করছে** — ইস্যুতে বাংলায় পুরো উত্তর, `AGENTS.md` পড়ে নিজের ভূমিকা বলেছে
- 🔑 **`OPENROUTER_API_KEY` ঠিকমতো পৌঁছেছে** (আগের "key নেই" রিপোর্টটা পুরনো রানের ছিল)
- 🏛️ হলঘর কাজ করছে: comment → workflow → উত্তর → comment

## ❌ যা ব্যর্থ হলো (আসল বার্তা)

| এজেন্ট | বার্তা |
|---|---|
| OpenCode | `Free usage limit reached. Connect a provider or subscribe to OpenCode Go…` |
| Cline | `Unauthorized: … re-authenticate your Cline account` |
| Hermes | বাইনারি নেই |
| OpenHands | (বন্ধ ছিল) |

## এই রানে যা বদলাল

- 🧹 `strip_ansi()` — Issue এ `◈[91m` এর মতো আবর্জনা আর আসবে না
- 🔁 **fallback কমান্ড** — "usage limit / unauthorized / credits" দেখলে দ্বিতীয় কমান্ড চেষ্টা করে
  - OpenCode → `--model openrouter/openrouter/free` (⚠️ এখনো যাচাই হয়নি)
- 🟦 Cline চালু — `-P openrouter -y` (key env থেকে)
- 🧪 ৫৪টা টেস্ট

## Verified

```
$ python3 -m unittest discover -s tests
Ran 54 tests in 0.028s
OK

$ python3 -m mesh.cli "হাই" --mode group --dry-run
[dry-run] opencode run --auto --model opencode/deepseek-v4.1-flash-free হাই
[dry-run] cline -P openrouter -y হাই
[dry-run] claude -p হাই
📊 মোট কল: 3 / 8
```

## Still open

1. **OpenCode** — হয় OpenRouter মডেল আইডি ঠিক করতে হবে (`openrouter/...` এর সঠিক রূপ), নয়তো ওর ফ্রি কোটা রিসেট হতে হবে
2. **Cline** — `-P openrouter` কাজ করে কি না পরের রানে দেখা হবে
3. **Hermes** — অফিশিয়াল ইনস্টল কমান্ড যাচাই করে `mesh.yml` এ বসানো
4. **OpenHands** — org/repo নিশ্চিত করে `@openhands` mention যাচাই
5. গ্রুপ মোডে উত্তর এলোমেলো আসে — চাইলে একটাই সারসংক্ষেপ comment বানানো যাবে

## Do not touch

- `max_calls_per_run` / `max_rounds` / `max_pair_calls` না বাড়িয়ে সমস্যা "ঠিক" করবেন না
- `redact()` সরাবেন না — comment এ key যাওয়া বন্ধ করে
- খালি উত্তরকে সফল বলবেন না (`empty` ফ্ল্যাগ) — এটাই আগের ভুল ধরেছিল
