# Handoff — ড্রয়ার মেনু ঠিক করা (2026-10-25)

**Asked:** মালিকের রিপোর্ট — এজেন্টদের জন্য বানানো PWA-তে ☰ ড্রয়ার মেনু কাজ করছে না (চ্যাট লিস্ট ও সেটিংস খোলা যায় না)।
**Priority:** 3 (AI-agent infrastructure / নিজের অ্যাপ)
**Role:** worker

**Done:**
- `docs/app/index.html` — drawer খোলার CSS ঠিক করা: `.drawer.on{transform:none}` এর বদলে `#sidebar.on,#settings.on{transform:translateX(0)}` (কারণ ব্যাখ্যা করে বাংলা কমেন্ট সহ)
- `tests/js/dom_check.mjs` — ড্রয়ার টেস্ট শক্ত করা: `class="on"` এর পাশাপাশি `getComputedStyle()` দিয়ে সত্যিকারের `transform` যাচাই
- `docs/pwa-bn.md` — "সমস্যা হলে" টেবিলে এই বাগের উপসর্গ/কারণ/সমাধান যোগ

**Verified:**
```
$ node tests/js/dom_check.mjs          # ঠিক করার পরে
✔ সাইডবার খোলে
✔ সাইডবার সত্যিই স্ক্রিনে আসে — transform=translateX(0)
✔ সাইডবার আবার বাইরে যায় — transform=translateX(-105%)
✔ সেটিংস ড্রয়ার সত্যিই স্ক্রিনে আসে — transform=translateX(0)
✅ সব DOM পরীক্ষা পাস

# আগের কোডে ফিরিয়ে একই টেস্ট (git stash দিয়ে) — বাগ ধরা পড়ে:
✖ সাইডবার সত্যিই স্ক্রিনে আসে — transform=translateX(-105%)
✖ সেটিংস ড্রয়ার সত্যিই স্ক্রিনে আসে — transform=translateX(105%)
❌ 2টা ব্যর্থ

$ python3 -m unittest discover -s tests
Ran 132 tests in 9.166s
OK
```

**কারণ (এক লাইনে):** `#sidebar{transform:translateX(-105%)}` (id = specificity 1,0,0) আর
`.drawer.on{transform:none}` (class = 0,2,0) — id জিতে যায়, তাই `on` ক্লাস বসার পরেও
ড্রয়ার বাইরেই থাকে; শুধু স্ক্রিম অন্ধকার হয়ে "কিছু হয়নি" মনে হয়।

**Still open:**
- কোনো কাজ বাকি নেই। ভবিষ্যতে তৃতীয় ড্রয়ার যোগ হলে তার জন্যও `#নতুনid.on{transform:translateX(0)}` লিখতে হবে (অথবা `.drawer.on` কে `!important` না দিয়ে id দিয়ে লিখুন)।

**Do not touch:**
- `.drawer`, `#scrim`, `z-index` (20/21) — এগুলো ঠিক আছে, এই বাগের সাথে সম্পর্ক নেই।
- `tests/js/dom_check.mjs` এর jsdom-নির্ভরতা: jsdom না থাকলে টেস্ট নিজেই বাদ পড়ে (CI ভাঙে না) — এটা ইচ্ছাকৃত।
