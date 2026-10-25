# Handoff — mesh health tools (2026-10-25)

**Asked:** "যেটা ভালো করো" — পরের সবচেয়ে দরকারি কাজটা নিজে বেছে নাও।
**Priority:** 3 (developer skills and AI-agent infrastructure)
**Role:** worker

**Done:**
- `mesh/doctor.py` — 🩺 স্বাস্থ্য পরীক্ষা: পাইথন, config, প্রতিটা এজেন্টের বাইনারি, key, store
- `mesh/cli.py` — দুইটা নতুন কমান্ড: `--doctor` (এক নজরে সব) আর `--probe` (কে সাড়া দেয়)
- `.github/workflows/ci.yml` — প্রতিটা push/PR এ টেস্ট + ডক্টর + দুইটা dry-run
- `.github/workflows/mesh.yml` — Node 22 যোগ, আসল প্যাকেজ নাম (`@opencode/cli`, `cline`, `@anthropic-ai/claude-code`), ডক্টর স্টেপ, `set -e` বাগ ঠিক
- `tests/test_mesh.py` — DoctorTest (৪টা নতুন টেস্ট), মোট ২৭
- `README.md` — কমান্ড টেবিল + নতুন ধাপ

**Verified:**
```
$ python3 -m unittest discover -s tests
Ran 27 tests in 0.015s

OK

$ python3 -m mesh.cli --doctor
 ✅ python                 3.11.2
 ✅ config/agents.json     5 এজেন্ট
 ⚠️ 🧑‍💻 OpenCode           opencode ইনস্টল নেই
 ❌ claude keys            OPENROUTER_API_KEY কোথাও নেই
 ✅ store                  .mesh/transcript.jsonl

$ python3 -m mesh.cli --probe --dry-run
 সাড়া দিয়েছে: 4/4
```

**এই মুহূর্তে ডক্টরের ফলাফল (এখানকার মেশিনে):** key নেই → ২টা ❌ (`claude`, `hermes`),
এজেন্ট ইনস্টল নেই → ৪টা ⚠️। এটাই প্রত্যাশিত; আসল রানে `OPENROUTER_API_KEY` বসালেই ✅ হবে।

**Still open:**
1. `OPENROUTER_API_KEY` GitHub Secrets এ বসানো — তারপর `--probe` দিয়ে আসল যাচাই
2. ⚠️ **প্রথম আসল রানে ফ্ল্যাগ যাচাই করতে হবে** — `opencode run --auto`, `cline -y`, `claude -p`,
   `hermes chat -q` — কোনোটা বদলালে শুধু `config/agents.json` এর `command` ঠিক করলেই হবে
3. ☤ Hermes এর অফিশিয়াল ইনস্টল কমান্ড `mesh.yml` এ কমেন্ট করা আছে — যাচাই করে খুলতে হবে
4. OpenHands এর org/repo নিশ্চিত করে `@openhands` mention যাচাই
5. ২৪/৭ চালু করতে `cron-job.org` → `workflow_dispatch` API কল

**Do not touch:**
- `config/agents.json` এর `max_calls_per_run` / `max_rounds` / `max_pair_calls` না বাড়িয়ে সমস্যা "ঠিক" করবেন না
- OpenHands কে গ্রুপ চ্যাটে (`chat` role) যোগ করবেন না — ওর ফ্রি কোটা দিনে ~১০
- key বা ছাত্রের ডেটা কোনো লগ/কমেন্টে নয়
