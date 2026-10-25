# Handoff — অ্যাপ কখন "রিয়েল" হবে + অপেক্ষার সময় ঠিক করা (2026-10-25)

**Asked:** মালিক জানতে চেয়েছেন — অ্যাপে (PWA) আসল এজেন্টের উত্তর কখন আসবে।
**Priority:** 3
**Role:** worker

**Done:**
- `worker/index.js` — `MAX_WAIT_MS` ৯০ সেকেন্ড → ফিক্সড কনস্টেন্ট বাদ, ডিফল্ট **৫ মিনিট** + `env.MAX_WAIT_MS` দিয়ে বদলানো যায়; প্রতি ২০ সেকেন্ডে `status` হৃদস্পন্দন ("এখনো কাজ চলছে… N সেকেন্ড")
- `worker/wrangler.toml` — `MAX_WAIT_MS` এর ব্যাখ্যা (কমেন্টে)
- `tests/js/worker_check.mjs` — টেস্ট env-এ `MAX_WAIT_MS: "2000"` (CI যেন ৫ মিনিট না আটকে থাকে)
- `docs/pwa-bn.md` — অপেক্ষার সময় আসল মাপ (৩–৯ মিনিট) সহ আপডেট
- `docs/index.html` — Pages root → `./app/` রিডাইরেক্ট (ছোট লিংক কাজ করে)

**Verified:**
```
$ node tests/js/worker_check.mjs
✅ Worker সব পরীক্ষায় পাস

$ python3 -m unittest discover -s tests
Ran 132 tests in 8.948s
OK

$ curl -o /dev/null -w '%{http_code}' https://rashelmahmudpc-create.github.io/agent-mesh-router/app/
200
```

**মালিককে জানানো দরকার (রিয়েল হওয়ার ৩ শর্ত):**
1. Cloudflare Worker ডিপ্লয়: `cd worker && npx wrangler deploy`
2. দুটো secret: `GITHUB_TOKEN` (Issues: Read & Write), `APP_TOKEN`
3. অ্যাপ → সেটিংস → সার্ভার = `https://mesh-chat.<নাম>.workers.dev`, টোকেন = APP_TOKEN → কানেকশন টেস্ট → 🟢

**Still open:**
- Worker এখনো ডিপ্লয় হয়েছে কি না রিপোতে কোনো প্রমাণ নেই (কোনো `workers.dev` ঠিকানা কোথাও লেখা নেই)। মালিক URL দিলে `/api/health` চেক করা যাবে।
- Actions রান কখনো ৯ মিনিটের বেশি নিলে অ্যাপে উত্তর আসবে না → তখন Issue-এ দেখতে হবে, অথবা পরে `/api/result` ধরনের "পরে এসে নাও" এন্ডপয়েন্ট বানানো যাবে (এখনো হয়নি)।

**Do not touch:**
- `MAX_WAIT_MS` খুব কম (৯০ সেকেন্ডের নিচে) করা যাবে না — Actions রান মাপা হয়েছে ২১৭s/৩৫৬s/৫৭০s।
- Worker-এর `GITHUB_TOKEN` কখনো অ্যাপ/ডকুমেন্টে বসানো যাবে না।
