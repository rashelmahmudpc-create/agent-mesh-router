# 🔑 সব secret-এর সত্যিকারের অবস্থা (২০২৬-১০-২৫)

> **কোথা থেকে:** GitHub Actions রান — [40193506705](https://github.com/rashelmahmudpc-create/agent-mesh-router/actions/runs/40193506705)
> **কীভাবে:** প্রতিটা key দিয়ে আসল API কল (OpenRouter `/api/v1/key`, Groq `/models`, Gemini `?key=`, OpenHands ক্লাউডে সত্যিকারের একটা conversation)।
> **🔒 কোনো key-এর মান কোথাও ছাপা হয় না — শুধু কাজ করছে কি না।**

## ✅ যেগুলো সত্যিই চলে

| secret | প্রমাণ |
|---|---|
| `OPENROUTER_API_KEY` | `/api/v1/key` → 200, `free_tier=true`, খরচ ≈ 0.00006 |
| `OPENROUTER_API_KEY_2` | `/api/v1/key` → 200, খরচ `0` (একদম তাজা কোটা) |
| `GROQ_API_KEY` | `/openai/v1/models` → 200 |
| `GEMINI_API_KEY` | `models?key=…` → 200 |
| `OPENHANDS_API_KEY` | ক্লাউডে sandbox খুলে আসল উত্তর: **“হ্যাঁ, আমি কাজ করছি — আপনার নির্দেশ পাওয়ার জন্য প্রস্তুত।”** |

## ⚠️ যেগুলো এই রিপোতে পৌঁছায় না

| secret | অবস্থা | মানে |
|---|---|---|
| `VERCEL_AI_GETAWAY` / `VERCEL_AI_GATEWAY` (+৩টা বানান) | ❌ খালি | ৫টা নাম-বানানই পরীক্ষা করা হয়েছে — কোনোটা এই workflow-এ আসে না। সম্ভবত secret টা **অন্য রিপোতে**, বা মান খালি, বা *Environment secret* (job-এ `environment:` লাগে)। |
| `GOOGLE_API_KEY` | ❌ খালি | বসানো নেই — `GEMINI_API_KEY` দিয়েই কাজ চলছে, দরকার নেই। |
| `CLINE_API_KEY` | 🖐️ | Cline-এর কোনো পাবলিক প্রোব endpoint নেই; Cline এখন `enabled=false`, তাই এটা দিয়ে কিছু চালানো হয় না। |
| `CARTESIA_API_KEY`, `CERTESIA_*`, `COMPOSIO_API_KEY`, `ADMISSIONSKY_*` | 🖐️ | এগুলো **অন্য প্রজেক্টের** key — mesh-router এদের ব্যবহারই করে না। |

## 🤖 এজেন্টরা আসলেই উত্তর দিচ্ছে

| এজেন্ট | ফল |
|---|---|
| 🧑‍💻 OpenCode | ✅ (নিজের ফ্রি মডেল) |
| 🟠 Claude Code | ✅ (`openrouter/free`) |
| ☤ Hermes | ✅ (reasoning বক্স বন্ধ করার পরে) |
| 🖐️ OpenHands | ✅ (ক্লাউডে সত্যিকারের conversation, দিনে একবার স্বয়ংক্রিয় যাচাই) |
| 🟦 Cline | ⏸️ বন্ধ (`enabled=false`) |

## 🔁 এখন কী নিজে থেকেই হয়

- প্রতিটা রানে **🔑 Key check** — ৫টা key-এর সত্যিকারের স্বাস্থ্য।
- **দিনে একবার** 🖐️ OpenHands লাইভ পরীক্ষা → সফল হলে `.mesh-openhands-ok`-এ তারিখ কমিট হয়ে যায়, তাই কোটা নষ্ট হয় না।
- ফ্রি মডেল তালিকা থেকে **১ টোকেনের পরীক্ষা** দিয়ে শুধু জীবিত মডেল বেছে নেওয়া হয় (মৃত মডেল আর এজেন্ট ভাঙবে না)।
