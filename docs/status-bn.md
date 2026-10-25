# 📊 মেশের অবস্থা (২০২৬-১০-২৫, ১৩:৪৫ UTC)

> লেখা হয়েছে শেষ রান [40193506705](https://github.com/rashelmahmudpc-create/agent-mesh-router/actions/runs/40193506705) আর তার পরের ফিক্সগুলোর ভিত্তিতে।

## ✅ এজেন্ট — কে সত্যিই উত্তর দেয়

| এজেন্ট | অবস্থা | প্রমাণ |
|---|---|---|
| 🧑‍💻 OpenCode | ✅ আসল উত্তর | নিজের ফ্রি মডেল (`deepseek-v4.1-flash-free`) |
| 🟠 Claude Code | ✅ আসল উত্তর | `openrouter/free` |
| ☤ Hermes | ✅ আসল উত্তর | শুধু ফ্রি মডেল, reasoning বক্স বন্ধ |
| 🖐️ OpenHands | ✅ আসল উত্তর | ক্লাউডে conversation: *"হ্যাঁ, আমি কাজ করছি…"* |
| 🟦 Cline | ⏸️ বন্ধ | `enabled=false` (ফ্রি টিয়ারে টোকেন কম) |

## 🔑 key-এর অবস্থা (আসল API কল দিয়ে)

| key | ফল |
|---|---|
| `OPENROUTER_API_KEY`, `OPENROUTER_API_KEY_2` | ✅ |
| `GROQ_API_KEY` | ✅ |
| `GEMINI_API_KEY` | ✅ |
| `OPENHANDS_API_KEY` | ✅ |
| Vercel (৫ বানান), `GOOGLE_API_KEY` | ❌ workflow-এ পৌঁছায় না |
| `CLINE_API_KEY` | 🖐️ প্রোব endpoint নেই |

বিস্তারিত: [`secret-check-bn.md`](secret-check-bn.md)

## 🖐️ OpenHands এখন গ্রুপ চ্যাটে (নতুন)

- `roles`-এ `chat` যোগ হয়েছে → priority 1 হিসেবে mesh রানেই উত্তর দেয়, আলাদা key-টেস্ট লাগে না।
- **দিনে সর্বোচ্চ ২টা conversation** (`daily_limit: 2`) — ওদের ফ্রি টিয়ার প্রায় ১০/দিন।
- হিসাব থাকে `.mesh-daily.json`-এ, প্রতিটা রানের শেষে কমিট হয়ে যায় → কোটা কখনো ভুলে যায় না।

## ⏰ কখন নিজে থেকে চলে

| ট্রিগার | কীভাবে |
|---|---|
| `.mesh-run` ফাইল বদলালে | push → mesh চলে (সবচেয়ে নির্ভরযোগ্য) |
| ৬ ঘণ্টায় একবার | `cron: "17 */6 * * *"` → 00:17, 06:17, 12:17, **18:17 UTC** |
| Issue #3-এ `@mesh …` | সাথে সাথে চলে |
| হাতে চালাতে | Actions → agent-mesh → Run workflow |

> ⚠️ শিডিউল এখনো একবারও চলে নি (ওয়ার্কফ্লো আজ তৈরি) — প্রথম সুযোগ আজ ১৮:১৭ UTC।
> ৬০ দিন কোনো কমিট না হলে GitHub শিডিউল বন্ধ করে দেয়; তখন [cron-job.org](https://cron-job.org) দিয়ে `workflow_dispatch` API কল করলেই চলবে।

## 🧪 টেস্ট

`python3 -m unittest discover -s tests` → **142 OK**

## 👉 আপনার দিক থেকে বাকি

- [ ] কিছু নেই — শুধু [Issue #3](https://github.com/rashelmahmudpc-create/agent-mesh-router/issues/3)-এ কাজ লিখে দিন
- [ ] (ঐচ্ছিক) Cline চালু করতে টোকেন বাজেট কমানো
- [ ] (ঐচ্ছিক) Vercel secret টা মুছে ফেলা — mesh এটা ব্যবহার করে না
