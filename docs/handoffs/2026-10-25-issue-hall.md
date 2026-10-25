# Handoff — issue hall + real CLI verification (2026-10-25)

**Asked:** "Next" — হ্যান্ডঅফের খোলা ধাপগুলো এগিয়ে নাও।
**Priority:** 3 (developer skills and AI-agent infrastructure)
**Role:** worker

**Done:**
- `mesh/issue.py` (নতুন) — 🏛️ হলঘর: `fetch_hall()` Issue এর আগের কথা পড়ে, `post_comment()` উত্তর লেখে, `redact()` key/টোকেন মোছে
- `mesh/router.py` — `group(message, history=...)`; Issue এর পুরনো আলোচনা প্রথম রাউন্ডের prompt এ যায়
- `mesh/adapters.py` — `$VAR` ফাঁকা হলে env সেট করে না (তবে literal `""` সেট হয় — OpenRouter এর শর্ত)
- `mesh/cli.py` — `--issue` এখন সত্যিই hall পড়ে + প্রতিটা সফল উত্তরের comment দেয়
- `.github/workflows/mesh.yml` — বটের comment আর `<!-- mesh:` চিহ্নযুক্ত comment এ ওয়ার্কফ্লো ওঠে না (লুপ বন্ধ); `CLAUDE_MODEL` ভেরিয়েবল
- `config/agents.json` — যাচাই করা তথ্য + `ANTHROPIC_MODEL`
- `README.md`, `ROADMAP.md` — হলঘরের নিয়ম ও অগ্রগতি যোগ
- `tests/test_mesh.py` — ৯টা নতুন টেস্ট (মোট **৩৬**)

**Verified — আসল CLI ইনস্টল করে:**

```
$ opencode --version
opencode v2.1.4
$ opencode run --help | grep -- --auto
  --auto                  Auto-approve permissions that are not explicitly denied
$ opencode run --auto "say OK"      # key ছাড়া, ডিফল্ট ফ্রি মডেল
> build · flint-40b-free
Error: ECONNRESET ...              EXIT_REAL=1   ← ব্যর্থতা ঠিকঠাক ধরা পড়ে

$ cline --version → 3.x (npm cline@3.0.73)
$ cline --help | grep -E "-y|--json"
  -y, --yolo   Auto-approve ... unsupervised runs (CI)
  --json       Output messages as JSON

$ claude --version → 2.1.310
$ claude -p "say OK"                    → "Not logged in · Please run /login"  EXIT=1
$ ANTHROPIC_BASE_URL=… ANTHROPIC_AUTH_TOKEN=… ANTHROPIC_API_KEY=  claude -p …
                                        → লগইন-গেট চলে যায় (কল শুরু হয়) ✅
```

⚠️ **গুরুত্বপূর্ণ:** `opencode` **key ছাড়াই** ডিফল্ট ফ্রি মডেল (`flint-40b-free`) দিয়ে চলে।
অর্থাৎ OpenCode এজেন্ট আজই কাজ করবে, কোনো secret ছাড়া।

**Verified — হলঘর (নকল `gh` দিয়ে end-to-end):**

```
$ PATH=/tmp/fakebin:$PATH python3 -m mesh.cli "@mesh হাই সবাই" --mode group --issue 42 --dry-run
🏛️ Issue #42 এর আগের আলোচনা পড়া হয়েছে (135 অক্ষর)
— রাউন্ড 1: opencode, cline, claude, hermes
✅ OpenCode / ✅ Cline / ✅ Claude Code / ✅ Hermes
[dry-run] gh issue comment 42 ← …  (৪টা)
📊 মোট কল: 4 / 8
```

**Verified — টেস্ট:**

```
$ python3 -m unittest discover -s tests
Ran 36 tests in 0.017s

OK
```

**Still open:**
1. `OPENROUTER_API_KEY` → GitHub Secrets (Claude Code + Hermes); তারপর `--probe` দিয়ে আসল যাচাই
2. `CLAUDE_MODEL` (Repository variable) — OpenRouter এর মডেল আইডি, যেমন `anthropic/claude-sonnet-4.6`
3. ☤ Hermes: অফিশিয়াল ইনস্টল কমান্ড `mesh.yml` এ কমেন্ট করা — যাচাই করে খুলতে হবে; `hermes chat -q` ফ্ল্যাগটা এখনো বাস্তবে যাচাই হয়নি
4. OpenHands: আসল org/repo নিশ্চিত করে `@openhands` mention যাচাই
5. `cline` — স্যান্ডবক্সে TLS সার্টিফিকেট সমস্যা; আসল GitHub Actions এ আবার দেখতে হবে (লগইনও লাগতে পারে)
6. ২৪/৭ চালু: `cron-job.org` → `workflow_dispatch`

**Do not touch:**
- `max_calls_per_run` / `max_rounds` / `max_pair_calls` না বাড়িয়ে সমস্যা "ঠিক" করবেন না
- `mesh/issue.py` এর `redact()` সরাবেন না — comment এ key যাওয়া বন্ধ করে
- OpenHands কে `chat` role এ যোগ করবেন না (দিনে ~১০ কোটা)
