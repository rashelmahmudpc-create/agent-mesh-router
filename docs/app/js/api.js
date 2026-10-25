/**
 * 🔌 সার্ভারের সাথে কথা বলা + ডেমো উত্তর
 *
 * লাইভ মোড: Worker (worker/index.js) → GitHub Issue-এ `@mesh ...` comment
 *           → Actions মেশ চালায় → উত্তরগুলো comment হয়ে ফিরে আসে
 * ডেমো মোড: সার্ভার নেই, তাই নিজের ভেতরের ছোট "ব্রেইন" দিয়ে উত্তর দেয়
 */

const TIMEOUT_MS = 20000;

export function normalizeBase(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const withScheme = /^https?:\/\//i.test(raw) ? raw : `https://${raw}`;
  return withScheme.replace(/\/+$/, "");
}

export function isLive(settings) {
  return Boolean(normalizeBase(settings?.apiBase));
}

function headers(settings) {
  return {
    "content-type": "application/json",
    "x-passcode": settings?.passcode || "",
  };
}

async function jsonFetch(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text }; }
    if (!res.ok) {
      const msg = (data && (data.error || data.message)) || `HTTP ${res.status}`;
      return { ok: false, error: msg, status: res.status };
    }
    return { ok: true, data };
  } catch (err) {
    const aborted = err && err.name === "AbortError";
    return { ok: false, error: aborted ? "সার্ভার সময়মতো উত্তর দেয়নি" : "ইন্টারনেট/সার্ভারে পৌঁছানো যায়নি" };
  } finally {
    clearTimeout(timer);
  }
}

/** 🩺 সার্ভার ঠিক আছে কি না */
export async function health(settings) {
  const base = normalizeBase(settings?.apiBase);
  if (!base) return { ok: false, error: "সার্ভার ঠিকানা দেওয়া হয়নি" };
  return jsonFetch(`${base}/api/health`, { headers: headers(settings) });
}

/** 📨 নতুন কথা পাঠানো */
export async function sendChat(settings, text) {
  const base = normalizeBase(settings?.apiBase);
  if (!base) return { ok: false, error: "ডেমো মোড" };
  return jsonFetch(`${base}/api/chat`, {
    method: "POST",
    headers: headers(settings),
    body: JSON.stringify({ text }),
  });
}

/** 📥 নতুন উত্তর আছে কি না (after = শেষ দেখা comment id, since = কখন থেকে দেখবে) */
export async function fetchReplies(settings, { after = 0, since = "" } = {}) {
  const base = normalizeBase(settings?.apiBase);
  if (!base) return { ok: false, error: "ডেমো মোড" };
  const query = new URLSearchParams({ after: String(after) });
  if (since) query.set("since", since);
  return jsonFetch(`${base}/api/messages?${query.toString()}`, {
    headers: headers(settings),
  });
}

/* ------------------------------------------------------------------ */
/* 🟡 ডেমো ব্রেইন — সার্ভার ছাড়াই অ্যাপ ব্যবহারযোগ্য রাখে            */
/* ------------------------------------------------------------------ */

const DEMO_ANSWERS = [
  {
    match: /অবস্থা|status|কী চলছে|কতদূর/i,
    text: [
      "**এখনকার অবস্থা (সংক্ষেপে)** 📊",
      "",
      "1. 🧑‍💻 **OpenCode** — ✅ কাজ করছে (ডিফল্ট কর্মী)",
      "2. 🟠 **Claude Code** — ✅ কাজ করছে, খালি উত্তর এলে ব্যাকআপ মডেল",
      "3. ☤ **Hermes** — 🆕 ইনস্টল হয়েছে, আসল রান বাকি",
      "4. 🟦 **Cline** — ⛔ টোকেন বাজেটের কারণে বন্ধ",
      "5. 🖐️ **OpenHands** — ⏸️ GitHub App বসালে চালু হবে",
      "",
      "> এটা **ডেমো উত্তর** — আসল এজেন্টের উত্তর পেতে সেটিংসে সার্ভার ঠিকানা দিন।",
    ].join("\n"),
  },
  {
    match: /কী করবো|কী করব|পরিকল্পনা|plan|সপ্তাহ/i,
    text: [
      "**এই সপ্তাহে ৩টা ছোট কাজ** 🗓️",
      "",
      "- ✅ মেশ চ্যাট অ্যাপটা iPhone-এ Add to Home Screen করে নিন",
      "- 🔌 চাইলে সার্ভার (Worker) বসিয়ে লাইভ করুন — ১০ মিনিটের কাজ",
      "- 📖 Actions-এর `🩺 mesh status log` Issue-এ উত্তরগুলো দেখে নিন",
      "",
      "বাকি সব এমনিতেই চলবে — আপনাকে কিছু করতে হবে না।",
    ].join("\n"),
  },
  {
    match: /রিপো|repo|ফাইল|কী আছে|গঠন/i,
    text: [
      "**রিপোর ভেতরে কী আছে** 📁",
      "",
      "- `mesh/` → ম্যানেজার (রাউটার) কোড",
      "- `config/agents.json` → কে কোন কাজ করবে",
      "- `AGENTS.md` → সব এজেন্টের একমাত্র নির্দেশনা",
      "- `web/` → 🆕 এই চ্যাট অ্যাপ (PWA)",
      "- `tests/` → অটো টেস্ট",
      "",
      "```text\npython3 -m unittest discover -s tests\n```",
    ].join("\n"),
  },
];

const DEMO_FALLBACK = [
  "বুঝেছি, স্যার ✅",
  "",
  "এটা **ডেমো মোড**, তাই আসল এজেন্টকে ডাকা হচ্ছে না। আপনার কথাটা এভাবে রাখলাম:",
  "",
  "> {text}",
  "",
  "আসল উত্তর পেতে **সেটিংস → সার্ভার ঠিকানা** দিন। তারপর এই একই কথা লিখলে OpenCode/Claude/Hermes উত্তর দেবে।",
];

/** ডেমো উত্তর — একটু দেরি করে দেয়, যেন আসল লাগে */
export function demoReply(text) {
  const found = DEMO_ANSWERS.find((item) => item.match.test(text));
  const body = found ? found.text : DEMO_FALLBACK.join("\n").replace("{text}", text.trim());
  const delay = 650 + Math.min(1500, text.length * 12);
  return new Promise((resolve) => {
    setTimeout(() => resolve({ ok: true, text: body, agent: "ডেমো" }), delay);
  });
}
