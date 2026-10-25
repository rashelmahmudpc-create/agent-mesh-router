# agent-mesh-router

A multi-agent orchestration framework for routing tasks across specialized agents, tools, and integrations.

## 🧠 Shared Brain

সব এজেন্টের জন্য একটাই নির্দেশনা-ফাইল: **[`AGENTS.md`](AGENTS.md)** (ZAYAN GLOBAL BRAIN v1.1)।

| এজেন্ট | কোথা থেকে পড়ে |
|---|---|
| Claude Code | `CLAUDE.md` → `AGENTS.md` |
| OpenCode / Codex / Hermes | `AGENTS.md` (নিজে থেকেই) |
| Cline | `.clinerules` → `AGENTS.md` |
| Gemini CLI | `GEMINI.md` → `AGENTS.md` |
| GitHub Copilot | `.github/copilot-instructions.md` |

> নিয়ম বদলাতে হলে **শুধু `AGENTS.md`** বদলান — বাকিগুলো কেবল পয়েন্টার।

**ব্রেইন এখানেই থাকে** — রাউটার কোড এই রিপোতে, GitHub Actions এ চলে।
পিসি, সার্ভার বা কার্ড কিছুই লাগে না। এজেন্টরা কাজ করে ওদের নিজের জায়গায়।

---

## 🚀 ৩ মিনিটে শুরু (বাংলা)

```bash
# ১) টিমে কারা আছে দেখুন
python3 -m mesh.cli --list

# ২) স্বাস্থ্য পরীক্ষা — কী ইনস্টল আছে, কোন key আছে
python3 -m mesh.cli --doctor

# ৩) কে সাড়া দেয়? (প্রতিটা এজেন্টকে এক লাইনের প্রশ্ন)
python3 -m mesh.cli --probe --dry-run

# ৪) নিজে একবার পরীক্ষা করুন — কিছুই চালাবে না, শুধু দেখাবে
python3 -m mesh.cli "হাই সবাই" --mode group --dry-run

# ৫) কাজ ভাগ করে দিন (একজনকে)
python3 -m mesh.cli "এই bug টা ঠিক করো" --mode direct

# ৬) গ্রুপ চ্যাট (সবাই উত্তর দেয়, কেউ কাউকে @mention করতে পারে)
python3 -m mesh.cli "হাই" --mode group
```

> 🔑 কোনো API key ছাড়াও **`--dry-run`** দিয়ে পুরো সিস্টেম পরীক্ষা করা যায়।

---

## 🧩 দুইটা মোড

| মোড | কী হয় | কখন |
|---|---|---|
| 🎯 `direct` | রাউটার ঠিক করে **কে করবে**, শুধু তাকেই ডাকে (ব্যর্থ হলে ব্যাকআপ) | আসল কাজ |
| 👥 `group` | সবাই একসাথে উত্তর দেয়; কেউ `@claude` লিখলে সে পরের রাউন্ডে উত্তর দেয় | আলোচনা / মত নেওয়া |

## 👥 গ্রুপ চ্যাট = GitHub Issue (হলঘর)

1. Issue এ লিখুন: `@mesh হাই সবাই`
2. `.github/workflows/mesh.yml` ওঠে → আগের **comment-গুলো পড়ে** (`mesh/issue.py` → `fetch_hall`)
3. সবাই একসাথে উত্তর দেয়, প্রতিটা উত্তর **comment** হয়ে Issue-তে ফিরে আসে
4. কেউ কাউকে `@claude` বললে পরের রাউন্ডে সে উত্তর দেয়

🛡️ নিরাপত্তা: প্রতিটা comment লেখার আগে **key/token মুছে ফেলা হয়** (`redact`)।
🔁 লুপ বন্ধ: বটের comment আর `<!-- mesh:… -->` চিহ্নযুক্ত comment ওয়ার্কফ্লো চালায় না।

## 🛡️ খরচ ও লুপ নিয়ন্ত্রণ

`config/agents.json` এর `settings`:

| সেটিং | অর্থ | ডিফল্ট |
|---|---|---|
| `max_rounds` | গ্রুপ চ্যাটে সর্বোচ্চ কত রাউন্ড | 3 |
| `max_calls_per_run` | এক রানে মোট সর্বোচ্চ কত কল | 8 |
| `max_pair_calls` | দুই এজেন্ট পরস্পরকে সর্বোচ্চ কতবার ডাকবে | 3 |

**Key ঘোরানো:** `OPENROUTER_API_KEY`, `OPENROUTER_API_KEY_2`, … — একটা key রেট-লিমিটে আটকালে
পরেরটা নিজে থেকেই ব্যবহার হয় (`mesh/keys.py`)। ২–৩টাই যথেষ্ট, বেশি ঘোরানো নিরাপদ নয়।

---

## 🧠 টিম (এবং কেন এমন)

| এজেন্ট | ধরন | মাথা | key লাগে? |
|---|---|---|---|
| 🧑‍💻 **OpenCode** | CLI | DeepSeek V4.1 Flash (OpenCode এর ভেতরে ফ্রি) | ❌ |
| 🟦 **Cline** | CLI | নিজের ফ্রি মডেল | ❌ |
| 🟠 **Claude Code** | CLI | OpenRouter দিয়ে যেকোনো মডেল | ✅ OpenRouter |
| ☤ **Hermes** | CLI | OpenRouter / নিজের পছন্দের মডেল | ✅ OpenRouter |
| 🖐️ **OpenHands** | GitHub Issue | ওদের ক্লাউডে ফ্রি | ❌ |

**সিদ্ধান্ত:** 🧠 ম্যানেজার = **আমাদের কোড** (কোনো AI কল নেই, ০ খরচ, ভুল করে না)।
Hermes ও বাকিরা = **কর্মী**। বিস্তারিত: [`docs/design-bn.md`](docs/design-bn.md)

---

## 💸 টাকা নেই? — সমস্যা নেই

| এজেন্ট | খরচ | কী লাগে |
|---|---|---|
| 🧑‍💻 OpenCode | **০** | কিছুই না — key ছাড়াই ফ্রি মডেল দিয়ে চলে ✅ |
| 🟦 Cline | **০** | নিজের ফ্রি মডেল |
| 🖐️ OpenHands | **০** | ওদের ক্লাউডে ফ্রি |
| 🟠 Claude Code | **০** | OpenRouter এর `:free` মডেল (কার্ড লাগে না) |
| ☤ Hermes | **০** | OpenRouter এর `:free` মডেল |

**ডিফল্ট মডেল = `openrouter/free`** (OpenRouter এর অটো-রাউটার — নিজেই একটা ফ্রি মডেল বেছে নেয়)।
`CLAUDE_MODEL` না দিলেও এটাই ব্যবহার হবে।

👉 বিস্তারিত: **[`docs/free-models-bn.md`](docs/free-models-bn.md)**

## 🔑 GitHub Secrets এ যা বসাতে হবে

```
OPENROUTER_API_KEY      # Claude Code + Hermes — কার্ড লাগে না (openrouter.ai/keys)
OPENROUTER_API_KEY_2    # (ঐচ্ছিক) ব্যাকআপ
GEMINI_API_KEY          # (ঐচ্ছিক) ভবিষ্যতের ছোট রাউটারের জন্য
XAI_API_KEY             # (ঐচ্ছিক) রিভিউয়ার / দ্বিতীয় মত
```

📋 Variable (ঐচ্ছিক): `CLAUDE_MODEL` = `openrouter/free` বা যেকোনো `:free` মডেল আইডি।

> 🚫 `GITHUB_TOKEN` এমনিতেই থাকে — `gh` দিয়ে Issue/comment করার জন্য।

---

## 🛠️ কমান্ড এক নজরে

| কমান্ড | কাজ |
|---|---|
| `python3 -m mesh.cli --list` | টিমে কারা আছে |
| `python3 -m mesh.cli --doctor` | 🩺 কী ইনস্টল, কোন key আছে, কী নেই |
| `python3 -m mesh.cli --probe` | 🔎 প্রতিটা এজেন্টকে ছোট প্রশ্ন — কে সাড়া দেয় |
| `python3 -m mesh.cli "..." --mode direct` | 🎯 কাজ ভাগ করে দেওয়া |
| `python3 -m mesh.cli "..." --mode group` | 👥 সবাই একসাথে |
| `--dry-run` | কিছুই চালাবে না, শুধু দেখাবে |
| `--issue N` | ওই Issue-কে হলঘর বানাও + উত্তর comment করো |
| `--json` | মেশিন-পাঠ্য আউটপুট |

`--doctor` এর ফল: ✅ ঠিক · ⚠️ সতর্কতা (এজেন্ট ইনস্টল নেই) · ❌ সমস্যা (key নেই)।

## 🗂️ ফোল্ডার

```
config/agents.json      # টিমের তালিকা (নতুন এজেন্ট যোগ এখানেই)
mesh/router.py          # 🧠 ম্যানেজার: direct + group, সীমা রক্ষা
mesh/adapters.py        # এজেন্টের সাথে কথা বলার সেতু (cli / github_issue)
mesh/keys.py            # key ঘোরানো
mesh/chat.py            # চ্যাটের লগ (.mesh/transcript.jsonl)
mesh/doctor.py          # 🩺 স্বাস্থ্য পরীক্ষা
tests/                  # ২৭টা পরীক্ষা — key ছাড়াই চলে
docs/handoffs/          # 📮 কাজের হ্যান্ডঅফ
.github/workflows/      # ব্রেইন যেখানে চলে (mesh.yml) + পরীক্ষা (ci.yml)
```

## ✅ পরীক্ষা

```bash
python3 -m unittest discover -s tests -v
```
