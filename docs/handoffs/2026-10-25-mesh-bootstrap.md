# Handoff — mesh bootstrap (2026-10-25)

**Asked:** একটা মাল্টি-এজেন্ট ম্যানেজার বানানো — পিসি/টাকা ছাড়া, GitHub Actions এ চলে; দুইটা মোড (direct + group); Hermes কর্মী; ব্রেইন GitHub এ।
**Priority:** 3 (developer skills and AI-agent infrastructure)
**Role:** worker

**Done:**
- `config/agents.json` — টিমের তালিকা (opencode, cline, claude, hermes, openhands)
- `mesh/router.py` — direct + group মোড, mention/keyword রাউটিং, লুপ ও খরচের সীমা
- `mesh/adapters.py` — CLI ও GitHub Issue সেতু
- `mesh/keys.py` — key rotation (429 হলে পরের key)
- `mesh/chat.py` — চ্যাটের লগ (`.mesh/transcript.jsonl`)
- `mesh/cli.py` — `python3 -m mesh.cli "..." --mode direct|group [--dry-run|--issue N]`
- `.github/workflows/mesh.yml` — Actions এ চালানোর ওয়ার্কফ্লো (Issue এ `@mesh` = গ্রুপ চ্যাট)
- `AGENTS.md` — ZAYAN GLOBAL BRAIN v1.1 (সব এজেন্টের একমাত্র নির্দেশনা)
- `CLAUDE.md`, `GEMINI.md`, `.clinerules`, `.github/copilot-instructions.md` — পয়েন্টার

**Verified:**
```
$ python3 -m unittest discover -s tests
Ran 21 tests in 0.015s

OK

$ python3 -m mesh.cli "হাই সবাই" --mode group --dry-run
✅ OpenCode / ✅ Cline / ✅ Claude Code / ✅ Hermes
📊 মোট কল: 4 / 8
```

**Still open:**
1. `OPENROUTER_API_KEY` GitHub Secrets এ বসানো (Claude Code + Hermes এর জন্য)
2. OpenHands এর সত্যিকারের org/repo নিশ্চিত করা, তারপর `@openhands` mention যাচাই
3. workflow এ `@opencode/cli` আর `cline` প্যাকেজের নাম ইনস্টল-টেস্ট করা (এখন `|| true` দিয়ে রাখা)
4. ২৪/৭ চালু করতে `cron-job.org` → `workflow_dispatch` API কল

**Do not touch:**
- `config/agents.json` এর `max_calls_per_run` / `max_rounds` / `max_pair_calls` না বাড়িয়ে সমস্যা "ঠিক" করবেন না
- OpenHands কে গ্রুপ চ্যাটে (`chat` role) যোগ করবেন না — ওর ফ্রি কোটা দিনে ~১০
- key বা ছাত্রের ডেটা কোনো লগ/কমেন্টে নয়
