# 📱 এজেন্ট টিম — iPhone-এ অ্যাপের মতো চ্যাট

**একটা ফাইলের PWA** (`docs/app/index.html`) — ChatGPT-স্টাইল চ্যাট, ভেতরে
ম্যানেজার/রিসার্চার/কোডার/ডিজাইনার/টেস্টার/রাইটার। ডেমো মোডে সার্ভার ছাড়াই চলে,
আর Worker দিলে আসল এজেন্টরা (OpenCode / Claude / Hermes) উত্তর দেয়।

| কী | কোথায় |
|---|---|
| অ্যাপের কোড | `docs/app/index.html` (vanilla HTML/CSS/JS, একটাই ফাইল) |
| সার্ভার (ঐচ্ছিক) | `worker/` (Cloudflare Worker, চুক্তি মেনে) |
| অটো টেস্ট | `tests/test_pwa.py`, `tests/js/` |

---

## ১️⃣ সবচেয়ে সহজ: ডেমো মোডে চালান (০ মিনিট)

`docs/app/index.html` খুললেই অ্যাপ চলে — কোনো সার্ভার, key বা ইন্টারনেট লাগে না।
উত্তরগুলো ভেতরের ছোট "ব্রেইন" থেকে আসে, তাই এগুলো **আসল এজেন্টের উত্তর নয়**।

```bash
python3 -m http.server 8080 --directory docs/app
# তারপর ব্রাউজারে: http://localhost:8080
```

## ২️⃣ iPhone-এ ইনস্টল (৩ ধাপ)

1. Safari-তে অ্যাপের ঠিকানা খুলুন
2. নিচের **Share** বাটন → **Add to Home Screen**
3. নাম "মেশ চ্যাট" → **Add**

এরপর হোম স্ক্রিনের আইকনে চাপ দিলে ব্রাউজার বার ছাড়াই খুলবে — সাধারণ অ্যাপের মতো। ✅

### ঠিকানা কোথা থেকে?

- **GitHub Pages (সহজ, কোনো টুলিং লাগে না):** Settings → Pages → Source = **Deploy from a branch**
  → Branch = `main`, Folder = **/docs** → Save।
  এক মিনিট পর ঠিকানা: `https://<ইউজারনেম>.github.io/agent-mesh-router/app/`
- চাইলে Cloudflare Pages-এও দেওয়া যায় (build command নেই, output folder = `docs/app`)

## ৩️⃣ লাইভ করা — আসল এজেন্টরা উত্তর দেবে (ঐচ্ছিক)

### Worker ডিপ্লয় (একবারের কাজ)

```bash
cd worker
npx wrangler deploy                     # প্রথমবার লগইন চাইবে
npx wrangler secret put GITHUB_TOKEN    # fine-grained PAT, শুধু Issues: Read & Write
npx wrangler secret put APP_TOKEN       # অ্যাপে যে টোকেন বসাবেন
```

`wrangler.toml`-এ `MESH_REPO` আর `MESH_ISSUE` বসিয়ে দিন (হলঘর Issue নম্বর)।

### অ্যাপে বসান

সেটিংস (⋯) → **সার্ভার** = `https://mesh-chat.<আপনার-নাম>.workers.dev`
→ **টোকেন** = `APP_TOKEN` → **কানেকশন টেস্ট**।
উপরের ব্যাজ 🟡 → 🟢 হয়ে গেলে লাইভ (ডেমো সুইচ নিজেই বন্ধ হবে)।

### চুক্তি (সংক্ষেপে)

| মেথড | পাথ | কাজ |
|---|---|---|
| GET | `/api/health` | ২০০ দিলেই সংযুক্ত |
| GET | `/api/agents` | এজেন্টের নাম/রোল/ইমোজি/রঙ |
| POST | `/api/upload` | ফাইল (এখন শুধু নাম-টাইপ ফেরে, ফাইল জমা হয় না) |
| POST | `/api/chat` | SSE স্ট্রিম: status · thinking · tool · tool_result · delta · final · typing · agent_message · error |

### ভেতরে কী ঘটে

1. অ্যাপ → Worker → Issue-এ comment: `@mesh আপনার কথা`
2. GitHub Actions মেশ চালায় → এজেন্টরা উত্তর দেয়
3. Worker ৩ সেকেন্ড পর পর comment দেখে, পেলেই স্ট্রিম করে অ্যাপে পাঠায়
   (সর্বোচ্চ ~৫ মিনিট অপেক্ষা — Actions রান মাপা হয়েছে ৩–৯ মিনিট; তার বেশি লাগলে
   Issue-এ গিয়ে উত্তর দেখা যাবে। অ্যাপে প্রতি ২০ সেকেন্ডে "এখনো কাজ চলছে…" দেখায়।)

> 💡 Issue comment থেকে ডাকা হলে মেশ **group** মোডে চলে। Worker সেটাকেই
> এজেন্ট মোডে সাজিয়ে এক উত্তর বানায়, গ্রুপ মোডে প্রত্যেকের আলাদা বাবল দেয়।

---

## 🔒 নিরাপত্তা

- GitHub টোকেন **কখনো অ্যাপে যায় না** — শুধু Worker-এর env-এ থাকে
- পাসকোড না মিললে Worker 401 দেয়
- চ্যাট শুধু আপনার ফোনের `localStorage`-এ জমা থাকে
- এজেন্টের লেখা মার্কডাউন আগে escape হয় → `<script>` কখনো চলে না

## 💰 খরচ

প্রতি মেসেজে **একটা Actions রান** হয় (৩টা এজেন্ট ≈ ৩টি রিকোয়েস্ট)।
পাবলিক রিপোতে Actions মিনিট ফ্রি; প্রাইভেট হলে মাসে ২০০০ মিনিটের হিসাব রাখুন।

## 🧪 টেস্ট

```bash
python3 -m unittest discover -s tests        # সব (Python + Node)
node tests/js/worker_check.mjs               # শুধু Worker (নকল GitHub দিয়ে)
npm i --no-save jsdom && node tests/js/dom_check.mjs   # আসল DOM পরীক্ষা
```

## 🔧 সমস্যা হলে

| উপসর্গ | কারণ | সমাধান |
|---|---|---|
| ☰ চাপলে পর্দা অন্ধকার হয় কিন্তু মেনু আসে না | `#sidebar`/`#settings`-এ দেওয়া `transform` CSS specificity-তে `.drawer.on`-কে হারিয়ে দেয় | id+class দিয়ে লিখতে হবে: `#sidebar.on,#settings.on{transform:translateX(0)}` (ঠিক করা হয়েছে) |
| মেনু খুললে পেছনের লেখা সরে যায় | ওভারলে/স্ক্রিম কাজ করছে না | `#scrim.on` আর ড্রয়ারের `z-index:21 > 20` দেখুন |

> ⚠️ ড্রয়ার ঠিক আছে কি না, শুধু `class="on"` দেখে বোঝা যায় না — `getComputedStyle`-এ
> `transform` সত্যিই `translateX(0)` হয়েছে কি না দেখতে হবে। `tests/js/dom_check.mjs` এখন সেটাই মাপে।
