# ☁️ Cloudflare — আমি সব করব, তুমি শুধু **১টা** মান বসাবে

> **কেন তোমাকে key দিতে হবে না:** আমার স্যান্ডবক্স থেকে `api.cloudflare.com`-এ নেটওয়ার্কই নেই (পরীক্ষা করে দেখেছি — ব্লকড)।
> তাই key আমাকে চ্যাটে দিলে **কিছুই হবে না**, শুধু ঝুঁকি বাড়বে।
> বদলে key টা **GitHub-এর secret**-এ রাখো — GitHub Actions-এর ইন্টারনেট আছে, সে-ই ডিপ্লয় করবে।

---

## 🎯 যা যা নিজে থেকেই হবে (তুমি হাত লাগাবে না)

```
তুমি ২টা secret বসাবে
        │
        ▼
GitHub Actions (worker.yml)
        │
        ├── ১. Worker টেস্ট চালাবে
        ├── ২. Cloudflare-এ deploy করবে
        ├── ৩. OPENROUTER / GROQ / GEMINI key বসিয়ে দেবে
        ├── ৪. ঠিকানা বের করে docs/app/server.json-এ লিখে দেবে
        │      → অ্যাপ নিজেই ঠিকানা নিয়ে নেবে, কিছু টাইপ করতে হবে না
        └── ৫. /api/health দিয়ে যাচাই করবে (fast=true)
```

---

## ১️⃣ Cloudflare API Token বানাও (একবার)

1. 👉 https://dash.cloudflare.com/profile/api-tokens
2. **Create Token** → নিচে **Edit Cloudflare Workers** → **Use template**
3. **Continue to summary** → **Create Token**
4. যা দেখাবে (`xxxxx…`) — **কপি করো**

## ২️⃣ ওটা GitHub-এ বসাও

> Account ID আর দিতে হবে না — ওয়ার্কফ্লো নিজেই খুঁজে নেয়।

👉 https://github.com/rashelmahmudpc-create/agent-mesh-router/settings/secrets/actions

**New repository secret** চেপে দুইবার:

| Name | Secret |
|---|---|
| `CF_API_TOKEN` | ১ ধাপে পাওয়া টোকেন |

> ⚠️ নাম **হুবহু** `CF_API_TOKEN` লিখো (বড় হাতের অক্ষর, আন্ডারস্কোর)।

---

## ৪️⃣ তারপর আমি বাকিটা চালিয়ে দেব

তুমি শুধু বলো **"বসিয়ে দিয়েছি"** — আমি একটা ছোট commit দিয়ে ডিপ্লয় শুরু করব,
তারপর রান দেখে তোমাকে ঠিকানা + ফল জানাব।

---

## 🔒 নিরাপত্তা

- টোকেন চ্যাটে দিও না, কোথাও স্ক্রিনশটও না।
- কাজ শেষ হলে টোকেন **Roll/Delete** করে দিতে পারবে: https://dash.cloudflare.com/profile/api-tokens
  (ডিপ্লয় হয়ে গেলে টোকেন মুছে দিলেও Worker চলবে — শুধু নতুন করে deploy করতে পারবে না)
- Worker-এ বসে যাওয়া key গুলো Cloudflare-এর secret হিসেবেই থাকে, কোডে বা রিপোতে যায় না।

---

## 🧪 কাজ শেষ হলে যাচাই

- `https://mesh-chat.<তোমার-সাবডোমেইন>.workers.dev/api/health`
  → `{"ok":true,"fast":true,"providers":["groq","openrouter","gemini"],...}`

## 🆘 কিছু আটকে গেলে

| লক্ষণ | কারণ | সমাধান |
|---|---|---|
| রানে `⏭️ ডিপ্লয় বাদ` | secret নাম মেলেনি | `CF_API_TOKEN` হুবহু লিখো |
| `Authentication error` | টোকেনে Workers permission নেই | টেমপ্লেট থেকে নতুন টোকেন |
| `fast:false` | provider key বসেনি | repo secret-এ OPENROUTER/GROQ/GEMINI আছে কি না দেখো |
| উত্তর আসে না | key-র কোটা | `/api/health`-এর `providers` দেখো |
