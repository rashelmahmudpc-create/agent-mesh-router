# 🖐️ OpenHands চালু করার একবারের সেটআপ (৫ মিনিট)

> OpenHands **আমাদের কোডে** চলে না — ওরা **ওদের নিজের সার্ভারে** চলে।
> আমরা শুধু একটা Issue-তে `@openhands` লিখে কাজ দিই, ওরা সেখানে comment করে উত্তর দেয়।
> এটা কাজ করতে **একবার** ওদের GitHub App বসাতে হবে।

---

## কেন এখন বন্ধ?

`config/agents.json` এ `openhands` আছে, কিন্তু `enabled: false`।
কারণ: ওদের GitHub App ইনস্টল না থাকলে `@openhands` কেউ পড়ে না → শুধু মিথ্যা ব্যর্থতা দেখাবে।

---

## ধাপে ধাপে

| # | কাজ |
|---|---|
| ১ | [**app.all-hands.dev**](https://app.all-hands.dev) এ যান → GitHub দিয়ে সাইন ইন |
| ২ | **Settings / Integrations** → **GitHub** → **Install GitHub App** |
| ৩ | রিপো বাছুন → **`rashelmahmudpc-create/agent-mesh-router`** (শুধু এই একটা) |
| ৪ | পারমিশন: Issues (read/write), Pull requests (read/write), Contents (read/write) |
| ৫ | Install চাপুন |
| ৬ | এই রিপোর [**Issue #3**](https://github.com/rashelmahmudpc-create/agent-mesh-router/issues/3) এ লিখুন: `@openhands এই রিপোতে কী কী ফাইল আছে দেখে জানাও` |
| ৭ | ওরা comment করলে বুঝবেন **ঠিকঠাক** — তখন `config/agents.json` এ `"enabled": true` করে দেবেন |

---

## ⚠️ খেয়াল রাখুন

- 🕐 OpenHands এর উত্তর **দেরিতে আসে** (কয়েক মিনিট) — আমাদের রান তখন শেষ হয়ে যাবে, উত্তর পরে comment হবে
- 💸 ওদের ফ্রি টিয়ারে **দিনে ~১০ conversation** — তাই ওকে গ্রুপ চ্যাটে নয়, শুধু **আসল কাজে** ডাকুন
- 🔒 আমাদের `redact()` এখানে কাজ করে না (ওরা নিজের সার্ভারে চলে) — তাই ওদের comment এ key দেবেন না

---

## চালু করার পর

```json
{
  "name": "openhands",
  "enabled": true
}
```

তারপর `python3 -m mesh.cli --doctor` চালালে দেখাবে `✅ 🖐️ OpenHands gh + token ঠিক আছে`।
