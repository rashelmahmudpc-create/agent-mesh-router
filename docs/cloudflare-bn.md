# ⚡ Cloudflare — ৮ মিনিটের বদলে ৩–৮ সেকেন্ড

> **কেন এত দ্রুত:** GitHub Actions প্রতিবার opencode/claude/hermes **ইনস্টল** করে (ওটাই ৮–১০ মিনিট)।
> Cloudflare-এ কোনো ইনস্টল নেই — চারটা এজেন্টের persona নিয়ে **সরাসরি মডেল API-তে সমান্তরালে** কল যায়।

```
আপনি লিখলেন
   │
   ▼
☁️ Cloudflare Worker ──┬── 🧑‍💻 OpenCode  → Groq
   (৪ কল একসাথে)         ├── 🟠 Claude    → OpenRouter
   ৩–৮ সেকেন্ড           ├── ☤ Hermes     → OpenRouter (key 2)
   │                     └── 🖐️ OpenHands → Gemini
   ▼
উত্তর সাথে সাথে অ্যাপে + Issue #3-এ comment (পেছনে)
```

---

## ১️⃣ Cloudflare অ্যাকাউন্ট (একবার)

👉 https://dash.cloudflare.com/sign-up — ইমেইল + পাসওয়ার্ড। **কার্ড লাগবে না।**

---

## ২️⃣ Worker বানান (ব্রাউজারেই, ২ মিনিট)

1. বাঁ দিকে **Workers & Pages** → **Create** → **Start with Hello World!** → **Deploy**
2. **Edit code** চাপুন → ভেতরের সব মুছে দিন → এই রিপোর [`worker/index.js`](../worker/index.js) **পুরোটা পেস্ট** করুন
3. **Deploy** চাপুন
4. উপরে ঠিকানা পাবেন: `https://mesh-chat.xxxxx.workers.dev` — **এটা কপি করে রাখুন**

---

## ৩️⃣ ৫টা Secret বসান

Worker → **Settings** → **Variables and Secrets** → **Add**

| নাম | কী | কোথায় পাবেন |
|---|---|---|
| `GITHUB_TOKEN` | উত্তর Issue #3-এ ফেরাতে | GitHub → Settings → Developer settings → Fine-grained token → **Issues: Read & Write** |
| `APP_TOKEN` | অ্যাপে বসানোর পাসকোড | নিজে যা খুশি লিখুন (যেমন `zayan-2026`) |
| `OPENROUTER_API_KEY` | ⚡ দ্রুত লেন | ইতিমধ্যে আছে |
| `GROQ_API_KEY` | ⚡ দ্রুত লেন | ইতিমধ্যে আছে |
| `GEMINI_API_KEY` | ⚡ দ্রুত লেন | ইতিমধ্যে আছে |

> 🔒 key গুলো শুধু Cloudflare-এ থাকবে — কোডে বা রিপোতে যাবে না।

---

## ৪️⃣ অ্যাপে ঠিকানা বসান

👉 https://rashelmahmudpc-create.github.io/agent-mesh-router/

**Settings** → **Server** ঘরে `https://mesh-chat.xxxxx.workers.dev` → **Save**
আর **Passcode** ঘরে `APP_TOKEN`-এর মান।

ব্যস। এখন কথা লিখলেই **৩–৮ সেকেন্ডে** চারজনের উত্তর। 🎉

---

## 🤖 চাইলে ডিপ্লয় নিজে থেকেই (কোড বদলালে আবার পেস্ট করতে হবে না)

GitHub → **Settings → Secrets and variables → Actions**-এ ২টা secret যোগ করুন:

| secret | কোথায় |
|---|---|
| `CF_API_TOKEN` | Cloudflare → My Profile → **API Tokens** → Create Token → **Edit Cloudflare Workers** |
| `CF_ACCOUNT_ID` | Cloudflare ড্যাশবোর্ডের ডান পাশে **Account ID** |

এরপর `worker/` ফোল্ডারে কিছু বদলালেই [`.github/workflows/worker.yml`](../.github/workflows/worker.yml) নিজে ডিপ্লয় করে দেবে।

---

## 🆚 দুই লেনের কাজ

| কাজ | কে করে | সময় |
|---|---|---|
| 💬 কথা, প্রশ্ন, পরামর্শ | ⚡ Cloudflare | ৩–৮ সেকেন্ড |
| 🛠️ ফাইল বদল, commit, PR, টেস্ট চালানো | 🐢 GitHub Actions / OpenHands | ৮–১০ মিনিট |

দুটোই একসাথে চলে। Cloudflare শুধু **কথার গতি** বাড়ায়।

---

## 🧪 যাচাই

- `node tests/js/worker_check.mjs` → দ্রুত লেনের টেস্টসহ সব পাস
- ব্রাউজারে খুলুন: `https://mesh-chat.xxxxx.workers.dev/api/health`
  → `{"ok":true,"fast":true,"providers":["groq","openrouter","gemini"],...}` দেখাবে

---

## 🛠️ যদি কিছু না চলে

| লক্ষণ | কারণ | সমাধান |
|---|---|---|
| `fast:false` | কোনো key বসেনি | ৩ ধাপে ৩টা key বসান |
| উত্তর আসে না, `error` | key ভুল/কোটা শেষ | `/api/health`-এ `providers` দেখুন |
| অ্যাপে "টোকেন ঠিক না" | `APP_TOKEN` মেলেনি | দুটো জায়গায় একই টোকেন দিন |
| Issue-এ comment আসে না | `GITHUB_TOKEN` নেই/কম পারমিশন | Issues: Read & Write দিন |
| পুরনো ধীর পথে ফিরতে চাই | — | `FAST=off` বসান |
