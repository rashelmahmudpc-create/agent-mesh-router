# 🔑 Key পুল — এক নজরে

## আপনার বর্তমান পরিস্থিতি

| key | কতগুলো | কোথায় |
|---|---|---|
| 🟣 `OPENROUTER_API_KEY` | ১টা | Claude Code + Hermes (+ OpenCode এর fallback) |
| 🟢 `GEMINI_API_KEY` | ১টা | ভবিষ্যতের ব্যাকআপ |
| 🖐️ `OPENHANDS_API_KEY` | ১টা | OpenHands ক্লাউড (priority 1) |

## কীভাবে কাজ করে

```
১. 🖐️ OpenHands   (priority 1 — ওদের ক্লাউড, আলাদা কোটা)
২. 🧑‍💻 OpenCode    (নিজের ফ্রি মডেল → OpenRouter → অটো-বাছাই করা ফ্রি মডেল)
৩. ☤ Hermes       (openrouter/free → FREE_M1 → FREE_M2 → opencode free)
৪. 🟠 Claude Code (সবার শেষে — সবচেয়ে দামি)
```

- একই key-তে **429 / quota / useless model** এলে key **১ ঘণ্টা কুলডাউনে** যায় (`.mesh/keystate.json`)
- পরের রানে কুলডাউনের key **পিছনে** চলে যায় — সময় নষ্ট হয় না
- একটা key-ই থাকলেও সমস্যা নেই; কুলডাউন শেষে আবার চেষ্টা হবে

## ⚠️ সীমা (সৎ কথা)

- OpenRouter ফ্রি: **দিনে ৫০ রিকোয়েস্ট** — এক key-তে এটাই ছাদ
- ৫০০ Gemini অ্যাকাউন্ট ঘোরানো **আমরা করব না** — শর্ত ভাঙা, অ্যাকাউন্ট বন্ধের ঝুঁকি
- তাই আসল সমাধান: **কাজের ভার OpenHands + OpenCode এর নিজের কোটা দিয়ে**

## কমান্ড

```bash
python3 -m mesh.cli --doctor            # কোন key আছে
python3 -m mesh.cli --openhands "হাই"   # ওদের ক্লাউড একবার পরীক্ষা
python3 -m mesh.cli --free-model-list 3 # আজকের ফ্রি মডেল
```
