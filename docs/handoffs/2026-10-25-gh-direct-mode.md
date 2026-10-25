# Handoff — GitHub সরাসরি মোড: Worker ছাড়াই আসল এজেন্ট (2026-10-25)

**Asked:** মালিক বলেছেন Cloudflare Worker ডিপ্লয় করতে পারবেন না — তবু অ্যাপে আসল এজেন্টের উত্তর চান।
**Priority:** 3
**Role:** worker

**Done:**
- `docs/app/index.html`
  - নতুন **GitHub সরাসরি** মোড: সেটিংসে `owner/repo` + `Issue নম্বর` + টোকেন বসালেই ব্রাউজার থেকে `api.github.com`-এ `@mesh …` comment যায় আর উত্তর পোল করে স্ট্রিম হয় (৫ মিনিট, ৩ সেকেন্ড পর পর, প্রতি ২০ সেকেন্ডে "এখনো কাজ চলছে…")
  - `isGh()` / `ghRun()` / `ghAgent()` / `ghHdr()` — আসল মেশ এজেন্টদের নাম-ইমোজি (`REAL_AGENTS`) সহ
  - `ping()` এখন GitHub মোডেও হেলথ চেক করে; চিপ দেখায় "GitHub-এ সংযুক্ত"
  - সেটিংসে টোকেন বসালে ডেমো নিজে থেকে বন্ধ হয়
- `tests/js/dom_check.mjs` — fetch নকল করে GH মোডের end-to-end টেস্ট (comment পোস্ট + উত্তর রেন্ডার)
- `tests/test_pwa.py` — allowlist-এ `api.github.com` যোগ
- `docs/pwa-bn.md` — "শুধু একটা টোকেন" পদ্ধতি (Worker পদ্ধতি বিকল্প হিসেবে নিচে)

**Verified:**
```
$ node tests/js/dom_check.mjs
✔ সাইডবার সত্যিই স্ক্রিনে আসে — transform=translateX(0)
...
✔ GitHub মোডে চিপ দেখায় — GitHub-এ সংযুক্ত
✔ Issue-এ @mesh comment গেছে
✔ GitHub থেকে আসল উত্তর এসেছে — ### 🟠 Claude Codeনমস্কার স্যার — আমি আস…
✔ এজেন্টের নাম/ইমোজি বসেছে
✔ GitHub মোডে JS এরর নেই
✅ সব DOM পরীক্ষা পাস

$ python3 -m unittest discover -s tests
Ran 132 tests in 9.288s
OK
```

**CORS প্রমাণ (এটাই এই মোড সম্ভব করার কারণ):**
```
$ curl -s -D - -H 'Origin: https://rashelmahmudpc-create.github.io' \
    https://api.github.com/repos/…/issues/3/comments | grep -i access-control-allow-origin
access-control-allow-origin: *
$ curl -s -D - -X OPTIONS -H 'Access-Control-Request-Headers: authorization,content-type' …
access-control-allow-methods: GET, POST, PATCH, PUT, DELETE
```

**Still open:**
- মালিককে একটা fine-grained PAT বানাতে হবে (শুধু এই রিপো, Issues: Read & write) — তারপর অ্যাপে বসিয়ে "GitHub টেস্ট"।
- Worker মোডও অক্ষত আছে — পরে চাইলে ব্যবহার করা যাবে।

**Do not touch:**
- টোকেন কোথাও কমিট/লগ/ডকে লিখবেন না; শুধু ফোনের `localStorage`-এ থাকবে।
- `ghQuietMs/ghPollMs/ghWaitMs` শুধু টেস্টের সুবিধার জন্য — আসল মান ১২s/৩s/৩০০s।
