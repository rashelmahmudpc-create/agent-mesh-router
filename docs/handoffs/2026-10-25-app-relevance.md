# Handoff — অ্যাপের চ্যাটে প্রাসঙ্গিক উত্তর (2026-10-25)

**Asked:** "এজেন্ট অ্যাপে প্রাসঙ্গিক উত্তর কেন দিচ্ছে না, আর ঠিকমতো কাজ কেন করছে না?"
**Priority:** 3 (AI-agent infrastructure)
**Role:** worker

## আসল কারণ (প্রমাণ সহ)

Actions রানের লগ (run 40218594334) ও Issue #3-এর comment থেকে দেখা গেছে:

1. **কাঁচা comment-ই প্রম্পট হয়ে যেত।** অ্যাপ যে comment পোস্ট করে: `@mesh আমি কি এগুলো বলতে বলছি… <!-- app:1792950773735 -->`।
   ওটাই এজেন্টের কাছে হুবহু যেত (লগে `MSG:` লাইনে দেখা যায়) — তাই এজেন্ট `@mesh` ডাক ফিরিয়ে লিখত
   ("@mesh হাই ভালো আছি"), আর `<!-- app:… -->` মার্কার নিয়ে বিভ্রান্ত হতো।
2. **হলঘরের ৯৯টা comment পটভূমি হিসেবে যেত** (`🏛️ Issue #3 এর আগের আলোচনা পড়া হয়েছে (3678 অক্ষর)`) —
   পুরনো, অসম্পর্কিত কথা। উপরন্তু নির্দেশনাটাই ছিল "উপরের আলোচনা পড়ে নিজের মত দাও" → এজেন্ট সারমর্ম লিখত
   ("@mesh-এর হলঘরের সংক্ষিপ্ত সারমর্ম"), প্রশ্নের উত্তর দিত না।
3. **অ্যাপের নিজের চ্যাট-স্মৃতি (history) পুরনো Actions পথে ব্যবহার হতো না** — তাই ফলো-আপ প্রশ্নের কনটেক্সট থাকত না।
4. **অ্যাপের "এজেন্ট" ট্যাবেও group মোড চলত** (লগে `▶️ mode=group`) — ৪ জন এজেন্ট + ৩ রাউন্ড → হট্টগোল, দেরি।
5. **Claude-এর চ্যাট সময়সীমা ১৫০ সেকেন্ড** — ফ্রি মডেল ধীর; সময় শেষে `❌ সাড়া দিতে পারিনি / সময় শেষ (150s)`
   (হলঘরে ৪ বার)। fallback মডেল একবারও চেষ্টা হতো না।

## Done

- `mesh/textutil.py` — নতুন `clean_prompt()`; `HTML_COMMENT_RE`, `MESH_CALL_RE` (মার্কার/`@mesh` বাদ)।
- `mesh/router.py` — `QUICK_HINT` এখন চ্যাট-চুক্তি (পরিচয় দিও না, রিপোর তালিকা দিও না, অনুমতি চেয়ে থেমো না);
  `_quick()` প্রম্পট পরিষ্কার করে; group মোডে **প্রশ্ন সবার শেষে**, পটভূমি আগে + "সারমর্ম দিও না"।
- `mesh/issue.py` — `fetch_hall()` comment থেকে মার্কার/`@mesh` বাদ দেয়, `FAILURE_MARKERS` লাইনগুলো (❌) বাদ দেয়, উল্টো ক্রমে (নতুন আগে) পড়ে।
- `mesh/adapters.py` — `MAX_TIMEOUT_TRIES = 2`: সময় শেষ হলে (code 124) পরের fallback মডেল একবার চেষ্টা করে,
  তারপর "⏱️ … সেকেন্ডের মধ্যে উত্তর আসেনি" বলে ছেড়ে দেয়।
- `mesh/cli.py` — নতুন `--no-hall` (অ্যাপ নিজেই আগের কথা পাঠায়)।
- `config/agents.json` — claude `chat_timeout_sec` 150 → 240 (নোটে কারণ লেখা)।
- `worker/index.js` — ধীর (Actions) পথে এখন অ্যাপের শেষ ৪ কথা `[আগের কথা]` ব্লকে যায় + `<!-- app:<ts> mode:agent|group -->` মার্কার।
- `docs/app/index.html` — GitHub সরাসরি পথেও একই mode মার্কার।
- `.github/workflows/mesh.yml` — মার্কার পড়ে মোড ঠিক করে: `mode:agent` → `direct`, নইলে `group`; অ্যাপ থেকে এলে `--no-hall`।
- `tests/test_mesh.py`, `tests/js/worker_check.mjs` — নতুন আচরণের টেস্ট (প্রম্পট পরিষ্কার, ক্রম, টাইমআউট fallback, fetch_hall ফিল্টার, মার্কার)।

## Verified

```
$ python3 -m unittest discover -s tests
Ran 177 tests in 0.827s
OK

$ node tests/js/worker_check.mjs
✔ 🧠 অ্যাপের আগের কথা সাথে যায়
✔ 🏷️ mode marker যায় (Actions এটা পড়ে direct চালাবে)
✔ 👥 group marker যায়
✅ Worker সব পরীক্ষায় পাস

$ bash (workflow-এর মোড-লজিক হুবহু কপি করে চালানো)
app=1 mode=direct args: --mode direct --issue 3 --no-hall     # অ্যাপ, এজেন্ট ট্যাব
app=1 mode=group  args: --mode group --issue 3 --no-hall      # অ্যাপ, গ্রুপ ট্যাব
app=0 mode=group  args: --mode group --issue 3                # হাতে লেখা comment (আগের আচরণ)

$ python3 -m mesh.cli '@mesh আজ কী করবো?\n<!-- app:1 mode:agent -->' --mode direct --issue 3 --no-hall --dry-run
opencode run --auto --model … আজ কী করবো?\n\n[সংক্ষিপ্ত নির্দেশ …] নিজের পরিচয় দিও না, রিপোর ফাইল-তালিকা দিও না …
📊 মোট কল: 1 / 8        # আগে: ৪ জন × ৩ রাউন্ড

$ node --check worker/index.js → OK ; docs/app/index.html এর ৪টা script block-ও node --check এ OK
```

## Still open

- অ্যাপ থেকে **নতুন একটা** প্রশ্ন পাঠিয়ে দেখতে হবে: উত্তর একজনের, প্রাসঙ্গিক, আর কত সেকেন্ড লাগে।
- Claude এখনো ২৪০ সেকেন্ডে না পারলে আগের মতোই ব্যর্থ দেখাবে (তবে বার্তা পরিষ্কার, আর একবার fallback চেষ্টা করে)।
- `worker/wrangler.toml` এর `FAST=off` স্যারের সিদ্ধান্ত — বদলানো হয়নি।

## Do not touch

- `config/agents.json` এর `max_calls_per_run` / `max_rounds` / `max_pair_calls` — কমানো/বাড়ানো নয়।
- `FAST=off` সিদ্ধান্ত (স্যার নিজে বদলাবেন)।
- Issue #3 পুরনো; ইতিহাস মুছবেন না (প্রমাণ হিসেবে দরকার)।