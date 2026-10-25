# Handoff — আসল এজেন্টের উত্তর দ্রুত (Groq নয়) (2026-10-25)

**Asked:** “Groq না — সরাসরি এজেন্টের উত্তর চাই” (এবং যত দ্রুত সম্ভব)।
**Priority:** 3
**Role:** worker

**Done:**
- `config/agents.json` — `chat_timeout_sec`: opencode **150**, claude **150**, hermes **120** (আসল কাজের `timeout_sec` ৬০০–৯০০ অপরিবর্তিত)
- `mesh/config.py` — `AgentSpec.chat_timeout_sec` + `timeout_for(quick)`
- `mesh/adapters.py` — `CliAdapter`/`build_adapter`-এ `timeout` ওভাররাইড
- `mesh/router.py` — `quick` মোড: `QUICK_HINT` (“সংক্ষেপে ৫–১০ লাইন, রিপো ঘাঁটাঘাঁটি নয়”) + ছোট timeout
- `mesh/cli.py` — `quick=bool(args.issue)` → অ্যাপ/Issue থেকে ডাকা মানেই চ্যাট, push/schedule রান আগের মতোই পূর্ণ
- `tests/test_mesh.py` — `FastChatTest` (৫টা নতুন টেস্ট)

**Verified:**
```
$ python3 -m unittest discover -s tests
Ran 140 tests in 9.438s
OK
```

**আসল মাপ (পুরোনো কোড, একই পাইপলাইন):**
- Issue comment রান `40202377234`: 14:28:14 → প্রথম এজেন্টের comment **14:43:23** = **১৫ মিনিট ৯ সেকেন্ড**, route step **465s**
- তাই কম সময়সীমা জরুরি ছিল: এখন route-এর সর্বোচ্চ = ~১৫০s ⇒ মোট সর্বোচ্চ ~৩ মিনিট, সাধারণত ১–২ মিনিট

**Still open:**
- লাইভ মাপা বাকি (dispatch/comment করার পারমিশন App-এর নেই: `actions:write` নেই, আর App-এর comment মেশ গ্রহণ করে না)। মালিক একটা মেসেজ দিলেই নতুন সময় মাপা যাবে।
- সত্যিকারের “সেকেন্ডে আসল এজেন্ট” চাইলে সর্বদা-চালু মেশিন লাগবে (নিজের PC ফ্রি, বা ~$5 VPS) + `worker/` ওখানে বসানো — টাকা/সিদ্ধান্ত মালিকের।

**Do not touch:**
- `max_calls_per_run`, `max_rounds`, `max_pair_calls` (AGENTS.md §13)।
- `timeout_sec` (৬০০–৯০০) — আসল কাজের জন্য দরকার; শুধু `chat_timeout_sec` কম।
