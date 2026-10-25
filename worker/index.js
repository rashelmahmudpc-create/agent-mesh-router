/**
 * 🔌 এজেন্ট টিম — ব্যাকএন্ড (Cloudflare Worker)
 *
 * ফ্রন্টএন্ডের চুক্তি অনুযায়ী চলে:
 *   GET  /api/health   → {ok:true, ...}
 *   GET  /api/agents   → [{id,name,role,emoji,color}]
 *   POST /api/upload   → multipart "file" → {id,name,type,url}
 *   POST /api/chat     → SSE / NDJSON ইভেন্ট স্ট্রিম
 *
 * ভেতরে কী হয়: অ্যাপের কথা GitHub Issue-এ `@mesh ...` comment হিসেবে যায়,
 * Actions-এর মেশ এজেন্টদের চালায়, উত্তরগুলো comment হয়ে ফিরে আসে — এখানেই
 * সেগুলো ধরে status / thinking / tool / delta / agent_message ইভেন্টে ঢালা হয়।
 *
 * 🔒 দরকারি env (সবই গোপন, অ্যাপে যায় না):
 *   GITHUB_TOKEN   → fine-grained PAT, Issues: Read & Write
 *   MESH_REPO      → owner/repo
 *   MESH_ISSUE     → হলঘর Issue নম্বর
 *   APP_TOKEN      → অ্যাপে বসানো Bearer টোকেন (না দিলে খোলা)
 *   ALLOWED_ORIGIN → ঐচ্ছিক, ডিফল্ট "*"
 */

const API = "https://api.github.com";
const MAX_TEXT = 4000;
// ⏱️ উত্তর কতক্ষণ অপেক্ষা করবে। Actions রান বাস্তবে ৩–৯ মিনিট নেয় (মাপা:
// 217s, 356s, 570s), তাই ডিফল্ট ১০ মিনিট। env.MAX_WAIT_MS দিয়ে বদলানো যায়।
const DEFAULT_MAX_WAIT_MS = 600000;

const cors = (env) => ({
  "access-control-allow-origin": env.ALLOWED_ORIGIN || "*",
  "access-control-allow-methods": "GET,POST,OPTIONS",
  "access-control-allow-headers": "authorization,content-type,x-passcode",
  "access-control-max-age": "86400",
});

const json = (data, status, env) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", ...cors(env) },
  });

function safeEqual(a, b) {
  const left = String(a || "");
  const right = String(b || "");
  if (!right || left.length !== right.length) return false;
  let diff = 0;
  for (let i = 0; i < left.length; i += 1) diff |= left.charCodeAt(i) ^ right.charCodeAt(i);
  return diff === 0;
}

function authOk(request, env) {
  if (!env.APP_TOKEN) return true;
  const header = request.headers.get("authorization") || "";
  const token = header.replace(/^Bearer\s+/i, "").trim();
  return safeEqual(token, env.APP_TOKEN);
}

async function gh(env, path, init = {}) {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      authorization: `Bearer ${env.GITHUB_TOKEN}`,
      accept: "application/vnd.github+json",
      "user-agent": "agent-team-worker",
      "x-github-api-version": "2022-11-28",
      ...(init.body ? { "content-type": "application/json" } : {}),
    },
  });
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text }; }
  return { ok: res.ok, status: res.status, data };
}

const issuePath = (env, suffix = "") => `/repos/${env.MESH_REPO}/issues/${env.MESH_ISSUE}${suffix}`;

const EMOJI = { opencode: "🧑‍💻", claude: "🟠", hermes: "☤", cline: "🟦", openhands: "🖐️" };
const ROLE = { opencode: "কোডিং", claude: "আর্কিটেকচার", hermes: "মেমরি", cline: "ফ্রন্টএন্ড", openhands: "বড় কাজ" };
const COLOR = { opencode: "#10b981", claude: "#d97757", hermes: "#6c8cff", cline: "#8b5cf6", openhands: "#f59e0b" };

function agentOf(comment) {
  const marker = /<!--\s*mesh:([\w.-]+)\s*-->/.exec(comment.body || "");
  const id = (marker ? marker[1] : comment.user?.login || "agent").toLowerCase();
  return {
    id,
    name: id.charAt(0).toUpperCase() + id.slice(1),
    role: ROLE[id] || "এজেন্ট",
    emoji: EMOJI[id] || "🤖",
    color: COLOR[id] || "#888888",
  };
}

const cleanBody = (body) =>
  String(body || "")
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/@mesh/g, "")
    .trim();

const isAgentComment = (row) => row.user?.type === "Bot" || /<!--\s*mesh:/.test(row.body || "");

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** আস্ত টেক্সট একবারে না পাঠিয়ে স্ট্রিমের মতো টুকরো টুকরো */
async function emitText(send, text, agent) {
  const size = 28;
  for (let i = 0; i < text.length; i += size) {
    const chunk = text.slice(i, i + size);
    send(agent ? { type: "agent_message", id: agent.streamId, agent, delta: chunk } : { type: "delta", text: chunk });
    await sleep(12);
  }
}

/* ---------------- এন্ডপয়েন্ট ---------------- */

async function handleHealth(env) {
  // ⚡ দ্রুত লেনের জন্য GitHub token জরুরি নয় — তাই health শুধু repo/issue দেখে।
  //    (token ছাড়া উত্তর Issue-এ জমা হবে না, কিন্তু চ্যাট চলবে)
  if (!env.MESH_REPO || !env.MESH_ISSUE) {
    return { ok: false, error: "Worker env ঠিক নেই (MESH_REPO / MESH_ISSUE)" };
  }
  const out = {
    ok: true,
    repo: env.MESH_REPO,
    issue: Number(env.MESH_ISSUE),
    title: "",
    fast: fastReady(env),
    providers: fastProviders(env),
    github: Boolean(env.GITHUB_TOKEN),
  };
  if (env.GITHUB_TOKEN) {
    const res = await gh(env, issuePath(env));
    if (res.ok) out.title = res.data?.title || "";
    else out.github = false;
  }
  return out;
}

function handleAgents() {
  return PERSONAS.map((p) => ({
    id: p.id,
    name: p.name,
    role: p.role,
    emoji: p.emoji,
    color: COLOR[p.id] || "#888888",
  }));
}

/**
 * 📎 আপলোড — এখানে আলাদা স্টোরেজ (R2/KV) নেই, তাই ফাইল রাখা হয় না।
 * ফাইলের নাম-টাইপ এজেন্টকে জানানো হয়, যাতে সে বুঝতে পারে কী পাঠানো হয়েছে।
 */
async function handleUpload(request) {
  const form = await request.formData();
  const file = form.get("file");
  if (!file || typeof file === "string") {
    return { status: 400, body: { error: "file ফিল্ড নেই" } };
  }
  return {
    status: 200,
    body: {
      id: `f${Date.now()}`,
      name: file.name || "file",
      type: file.type || "application/octet-stream",
      url: "",
      note: "ফাইল সংরক্ষণ করা হয়নি (স্টোরেজ নেই) — শুধু নাম এজেন্টকে জানানো হয়েছে",
    },
  };
}

function sse(env, run) {
  const encoder = new TextEncoder();
  let closed = false;
  const stream = new ReadableStream({
    async start(controller) {
      const send = (event) => {
        if (closed) return;
        try {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
        } catch {
          closed = true;
        }
      };
      try {
        await run(send);
      } catch (err) {
        send({ type: "error", message: `সার্ভারে সমস্যা: ${String(err).slice(0, 160)}` });
      }
      closed = true;
      try { controller.close(); } catch {}
    },
    cancel() {
      closed = true;
    },
  });
  return new Response(stream, {
    status: 200,
    headers: {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-cache, no-transform",
      connection: "keep-alive",
      "x-accel-buffering": "no",
      ...cors(env),
    },
  });
}


/* ================= ⚡ দ্রুত লেন — সরাসরি মডেল API =================
 *
 * কেন: Actions রান ৮–১০ মিনিট নেয়, কারণ প্রতিবার opencode/claude/hermes ইনস্টল হয়।
 * এখানে কোনো ইনস্টল নেই — চারটা এজেন্টের persona নিয়ে সরাসরি মডেল API-তে
 * **সমান্তরালে** কল যায়, তাই উত্তর ৩–৮ সেকেন্ডে। উত্তর সাথে সাথে SSE-তে যায়,
 * আর Issue #3-এ comment পোস্ট হয় পেছনে (ctx.waitUntil), যাতে অপেক্ষা না বাড়ে।
 *
 * env:
 *   FAST=off                     → পুরনো Actions পথ
 *   OPENROUTER_API_KEY (+_2) / GROQ_API_KEY / GEMINI_API_KEY
 *   FAST_MODEL_OPENROUTER / FAST_MODEL_GROQ / FAST_MODEL_GEMINI
 *   FAST_TIMEOUT_MS              → ডিফল্ট ২০০০০
 */

const FAST_RULES = [
  "তুমি সহজ বাংলায় উত্তর দাও, স্যার সম্বোধন করে।",
  "প্রথম বাক্যেই সরাসরি উত্তর — ব্যবহারকারী যা জিজ্ঞেস করেছে তার উত্তর।",
  "কখনো নিজের বিশ্লেষণ, পরিকল্পনা, ধাপ বা চিন্তা লিখবে না — শুধু চূড়ান্ত উত্তর দেবে।",
  "প্রশ্ন ছোট হলে উত্তরও ছোট (১–২ লাইন)। সর্বোচ্চ ৪–৫ লাইন।",
  "কোনো মেনু, সম্ভাব্য কাজের তালিকা বা \"আমি কী কী করতে পারি\" জাতীয় কথা দিও না — শুধু যা জিজ্ঞেস করা হয়েছে।",
  "যা জানো না তা বানিও না; দরকার হলে এক লাইনে বলো কী তথ্য লাগবে।",
  "কোনো secret, key বা পাসওয়ার্ড কখনো লিখো না।",
].join(" ");

const PERSONAS = [
  {
    id: "opencode", emoji: "🧑‍💻", name: "OpenCode", role: "কোডিং",
    chain: ["groq", "openrouter", "gemini"],
    style: "তুমি OpenCode — দলের কোডিং worker। কোড লাগলে সংক্ষিপ্ত, চালু-করা-যায় এমন কোড দাও।",
  },
  {
    id: "claude", emoji: "🟠", name: "Claude Code", role: "আর্কিটেকচার",
    chain: ["openrouter", "groq", "gemini"],
    style: "তুমি Claude Code — আর্কিটেকচার ও পর্যালোচনার এজেন্ট। দুইটা বিকল্প দিয়ে দ্বিধা ভাঙো।",
  },
  {
    id: "hermes", emoji: "☤", name: "Hermes", role: "মেমরি",
    chain: ["openrouter", "groq", "gemini"],
    style: "তুমি Hermes — স্মৃতি ও পরিকল্পনার এজেন্ট। সিদ্ধান্ত মনে রাখো, ধাপে ধাপে বলো।",
  },
  {
    id: "openhands", emoji: "🖐️", name: "OpenHands", role: "বড় কাজ",
    chain: ["groq", "openrouter", "gemini"],
    style: "তুমি OpenHands — বড় কাজের এজেন্ট। কাজটা ছোট ধাপে ভাগ করে প্রথম ধাপটা বলো।",
  },
];

const PROVIDERS = {
  groq: {
    url: () => "https://api.groq.com/openai/v1/chat/completions",
    key: (env) => env.GROQ_API_KEY,
    model: (env) => env.FAST_MODEL_GROQ || "llama-3.3-70b-versatile",
    models: (env) => (env.FAST_MODEL_GROQ
      ? [env.FAST_MODEL_GROQ]
      : ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "openai/gpt-oss-120b"]),
    headers: (key) => ({ "content-type": "application/json", authorization: `Bearer ${key}` }),
    body: (env, model, system, user, history = []) => ({
      model,
      messages: [{ role: "system", content: system }, ...history, { role: "user", content: user }],
      max_tokens: 400,
      temperature: 0.3,
    }),
    parse: (d) => d?.choices?.[0]?.message?.content,
  },
  openrouter: {
    url: () => "https://openrouter.ai/api/v1/chat/completions",
    key: (env, persona) => {
      // 🔑 দুইটা OpenRouter key আছে — Hermes দ্বিতীয়টা ব্যবহার করবে (429 ছড়াবে না)
      const first = env.OPENROUTER_API_KEY || "";
      const second = env.OPENROUTER_API_KEY_2 || "";
      if (persona && persona.id === "hermes") return second || first;
      return first || second;
    },
    model: (env) => env.FAST_MODEL_OPENROUTER || "openrouter/free",
    models: (env) => (env.FAST_MODEL_OPENROUTER
      ? [env.FAST_MODEL_OPENROUTER]
      : ["openrouter/free", "meta-llama/llama-3.3-70b-instruct:free", "deepseek/deepseek-chat-v3.1:free"]),
    headers: (key) => ({
      "content-type": "application/json",
      authorization: `Bearer ${key}`,
      "http-referer": "https://github.com/rashelmahmudpc-create/agent-mesh-router",
      "x-title": "agent-mesh-router",
    }),
    body: (env, model, system, user) => ({
      model,
      messages: [{ role: "system", content: system }, ...history, { role: "user", content: user }],
      max_tokens: 400,
      temperature: 0.3,
      reasoning: { exclude: true }, // 🧠 ভেতরের চিন্তা ফেরত দিও না
    }),
    parse: (d) => d?.choices?.[0]?.message?.content,
  },
  gemini: {
    url: (env, model) => `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`,
    // Gemini-র মডেল নাম বদলায় — তাই একাধিক চেষ্টা (উপরের models() দেখুন)
    key: (env) => env.GEMINI_API_KEY,
    model: (env) => env.FAST_MODEL_GEMINI || "gemini-2.5-flash",
    models: (env) => (env.FAST_MODEL_GEMINI
      ? [env.FAST_MODEL_GEMINI]
      : ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"]),
    headers: (key) => ({ "content-type": "application/json", "x-goog-api-key": key }),
    body: (env, model, system, user, history = []) => ({
      systemInstruction: { parts: [{ text: system }] },
      contents: [
        ...history.map((h) => ({ role: h.role === "assistant" ? "model" : "user", parts: [{ text: h.content }] })),
        { role: "user", parts: [{ text: user }] },
      ],
      generationConfig: {
        maxOutputTokens: 400,
        temperature: 0.3,
        thinkingConfig: { thinkingBudget: 0 }, // 🧠 চিন্তা বন্ধ
      },
    }),
    parse: (d) => (d?.candidates?.[0]?.content?.parts || []).map((p) => p.text || "").join(""),
  },
};

/** কোন provider-গুলো এই মুহূর্তে চাবি পেয়েছে */
function fastProviders(env) {
  return Object.keys(PROVIDERS).filter((name) => Boolean(PROVIDERS[name].key(env)));
}

/** ⚡ দ্রুত লেন চালু? (key থাকলে + FAST=off না হলে) */
function fastReady(env) {
  return String(env.FAST || "").toLowerCase() !== "off" && fastProviders(env).length > 0;
}

// 🧹 মডেলের "Analize the Request / Attempt 1 / Constraint" জাতীয় ভেতরের কথা বাদ দিই
const META_PREFIX = /^\s*(?:[\d]+[.)]\s*)?(?:analy[sz]e|analysis|constraints?|constraint check|drafting|draft|attempt\s*\d|internal monologue|monologue|let me|hmm\b|thinking|reasoning|step\s*\d|plan\b|understanding|user\s*:|language\s*:|tone\/style|tone\s*:|length\s*:|structure\s*:|goal\s*:|task\s*:|বিশ্লেষণ|পরিকল্পনা|চিন্তা)\b/i;
const ANSWER_MARKERS = /^(?:সারমর্ম|উত্তর|সংক্ষেপে|এক কথায়|আসসালামু|হ্যালো|হাই|স্যার)/;

function cleanAnswer(text) {
  let out = String(text || "")
    .replace(/<\s*(?:thinking|analysis|reasoning)[\s\S]*?<\s*\/\s*(?:thinking|analysis|reasoning)\s*>/gi, "")
    .replace(/^\s*(?:analysis|reasoning|thinking)\s*:\s*/gim, "");
  const lines = out.split("\n");
  // প্রথমে যেখানে আসল উত্তর শুরু ("সারমর্ম"/সালাম), সেখান থেকে রাখি
  const start = lines.findIndex((l) => ANSWER_MARKERS.test(l.trim()));
  let kept = (start > 0 ? lines.slice(start) : lines)
    .filter((line) => {
      const t = line.trim();
      if (!t) return true;
      if (META_PREFIX.test(t) && !ANSWER_MARKERS.test(t)) return false;
      return true;
    })
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  // কিছু না থাকলে শেষ অনুচ্ছেদটাই দিই
  if (kept.length < 12) {
    const paras = String(text || "").split(/\n\s*\n/).map((x) => x.trim()).filter(Boolean);
    const last = paras[paras.length - 1] || "";
    const cleaned = last.split("\n").filter((l) => !META_PREFIX.test(l.trim())).join("\n").trim();
    kept = cleaned || String(text || "").trim();
  }
  return kept
    .replace(/^\s*(?:সারমর্ম|সংক্ষেপে|উত্তর)\s*[:：]\s*/i, "")
    .trim()
    .slice(0, 1600);
}

/** 🤖 কোন এজেন্ট উত্তর দেবে — agent মোডে একজনই; drop-down এ বাছা থাকলে শুধু তারাই */
function pickPersona(message, mode, agents) {
  // 🎯 অ্যাপের drop-down: একজনে টিক = শুধু সে, একাধিকে = সবাই
  const want = (Array.isArray(agents) ? agents : [])
    .map((x) => String(x || "").trim().toLowerCase())
    .filter(Boolean);
  if (want.length) {
    const chosen = PERSONAS.filter((p) => want.includes(p.id));
    if (chosen.length) return mode === "group" ? chosen : [chosen[0]];
  }
  if (mode === "group") return PERSONAS.slice();
  const low = String(message || "").toLowerCase();
  const rules = [
    ["hermes", ["মনে", "মেমরি", "নোট", "note", "remember", "memory", "plan", "পরিকল্পনা", " checklist"]],
    ["claude", ["আর্কিটেকচার", "architecture", "review", "রিভিউ", "ডিজাইন", "design", "কেন", "why", "তুলনা", "compare"]],
    ["openhands", ["রিপো", "repo", "pr", "issue", "ফাইল", "file", "বড়", "big", "ডিপ্লয়", "deploy", "প্রজেক্ট"]],
    ["opencode", ["কোড", "code", "বাগ", "bug", "error", "এরর", "ফিক্স", "fix", "টেস্ট", "test", "ইনস্টল", "install"]],
  ];
  for (const [id, words] of rules) {
    if (words.some((w) => low.includes(w))) return [PERSONAS.find((p) => p.id === id)];
  }
  return [PERSONAS.find((p) => p.id === "opencode")]; // ডিফল্ট
}

function personaAgent(persona) {
  return {
    id: persona.id,
    name: persona.name,
    emoji: persona.emoji,
    role: persona.role,
    color: COLOR[persona.id] || "#888888",
  };
}

/** একটা এজেন্টের উত্তর — provider চেইন ধরে, সময় শেষ হলে ছেড়ে দেয় */
async function askModel(env, persona, message, history = []) {
  const timeout = Number(env.FAST_TIMEOUT_MS) || 20000;
  const system = `${FAST_RULES}\n\n${persona.style}\n\nতোমার নাম ${persona.name} (${persona.emoji})।`;
  const failures = [];
  for (const name of persona.chain) {
    const provider = PROVIDERS[name];
    const key = provider.key(env, persona);
    if (!key) {
      failures.push(`${name}: key নেই`);
      continue;
    }
    const models = (provider.models ? provider.models(env) : [provider.model(env)]).filter(Boolean);
    for (const model of models) {
      const started = Date.now();
      try {
        const res = await fetch(provider.url(env, model), {
          method: "POST",
          headers: provider.headers(key),
          body: JSON.stringify(provider.body(env, model, system, message, history)),
          signal: AbortSignal.timeout(timeout),
        });
        const raw = await res.text();
        let data = null;
        try { data = raw ? JSON.parse(raw) : null; } catch { data = null; }
        if (!res.ok) {
          // 🩺 আসল কারণটা ছোট করে রাখি (key কখনো নয়)
          const why = ((data && data.error && (data.error.message || data.error)) || raw || "")
            .toString().slice(0, 90);
          failures.push(`${name}/${model}: HTTP ${res.status}${why ? ` · ${why}` : ""}`);
          continue; // পরের মডেল
        }
        const out = cleanAnswer(provider.parse(data));
        if (!out) {
          failures.push(`${name}/${model}: খালি উত্তর`);
          continue;
        }
        return { ok: true, text: out, provider: name, model, ms: Date.now() - started };
      } catch (err) {
        failures.push(`${name}/${model}: ${String(err).slice(0, 60)}`);
      }
    }
  }
  return { ok: false, text: "", provider: "", ms: 0, failures };
}

/** উত্তরে কী কী model/key লেগেছে — কোথাও key ছাপা হয় না */
async function postAnswers(env, rows) {
  if (!env.GITHUB_TOKEN || !env.MESH_REPO || !env.MESH_ISSUE) return { posted: 0 };
  let posted = 0;
  await Promise.all(
    rows.map(async (row) => {
      const body =
        `<!-- mesh:${row.agent.id} -->\n**${row.agent.emoji} ${row.agent.name}**\n\n${row.text}` +
        `\n\n_⚡ দ্রুত লেন · ${row.provider} · ${row.ms}ms_`;
      const res = await gh(env, issuePath(env, "/comments"), {
        method: "POST",
        body: JSON.stringify({ body }),
      });
      if (res.ok) posted += 1;
    }),
  );
  return { posted };
}

/** ⚡ মূল দ্রুত পথ — agent মোডে একজন, group মোডে সবাই (সমান্তরালে) */
async function handleFastChat(env, ctx, payload) {
  const text = String(payload?.message || "").trim();
  const mode = payload?.mode === "group" ? "group" : "agent";
  const names = (Array.isArray(payload?.attachments) ? payload.attachments : [])
    .map((f) => f?.name)
    .filter(Boolean);
  const question = `${text}${names.length ? `\n\n📎 সংযুক্ত ফাইল: ${names.join(", ")}` : ""}`;
  // 🧠 আগের কথা মনে রাখি (সর্বোচ্চ ৬ পাতা) — উত্তর প্রাসঙ্গিক থাকে
  const history = (Array.isArray(payload?.history) ? payload.history : [])
    .filter((h) => h && typeof h.text === "string" && h.text.trim())
    .slice(-6)
    .map((h) => ({ role: h.role === "assistant" ? "assistant" : "user", content: h.text.slice(0, 600) }));
  const picked = pickPersona(text, mode, payload?.agents);
  const startedAt = Date.now();

  return sse(env, async (send) => {
    const providers = fastProviders(env);
    // 👤 agent মোডে একজনই উত্তর দেয়, 👥 group মোডে সবাই
    send({
      type: "status",
      text: mode === "group" ? "⚡ সবাইকে জিজ্ঞেস করছি…" : "⚡ উত্তর তৈরি হচ্ছে…",
    });
    // 🧽 ভেতরের provider-এর নাম ব্যবহারকারীকে দেখাই না
    send({ type: "tool", id: "fast", name: "উত্তর তৈরি হচ্ছে", state: "running" });

    const answered = [];
    const single = mode !== "group";

    await Promise.all(picked.map(async (persona) => {
      const agent = personaAgent(persona);
      const result = await askModel(env, persona, question, history);
      if (!result.ok) {
        send({ type: "status", text: `${agent.emoji} ${agent.name}: উত্তর পাওয়া যায়নি, অন্য পথে চেষ্টা করছি…` });
        return;
      }
      if (single) {
        // একজনের উত্তর — সাধারণ delta হিসেবে (অ্যাপে একটা পরিষ্কার বাবল)
        agent.streamId = `f${persona.id}${Date.now()}`;
        await emitText(send, result.text, null);
      } else {
        agent.streamId = `f${persona.id}${Date.now()}`;
        send({ type: "typing", agent });
        await emitText(send, result.text, agent);
        send({ type: "agent_message", id: agent.streamId, agent, text: result.text });
      }
      answered.push({ agent, text: result.text, provider: result.provider, ms: result.ms });
    }));

    send({
      type: "tool_result",
      id: "fast",
      output: `${answered.length}টি উত্তর · ${((Date.now() - startedAt) / 1000).toFixed(1)} সেকেন্ড`,
    });

    if (single && answered.length) send({ type: "final", text: answered[0].text });
    if (!answered.length) {
      send({
        type: "error",
        message: "কোনো মডেল উত্তর দিল না — key (OPENROUTER/GROQ/GEMINI) দেখুন, বা FAST=off করে Actions পথ ব্যবহার করুন",
      });
    }

    // 📮 Issue #3-এ পেছনে পোস্ট — উত্তরের গতি যেন না কমে
    const job = postAnswers(env, answered);
    if (ctx && typeof ctx.waitUntil === "function") ctx.waitUntil(job);
    else await job;
  });
}


async function handleChat(request, env, ctx) {
  let payload;
  try { payload = await request.json(); } catch { return json({ error: "JSON ঠিক নেই" }, 400, env); }

  const text = String(payload?.message || "").trim();
  const mode = payload?.mode === "group" ? "group" : "agent";
  const files = Array.isArray(payload?.attachments) ? payload.attachments : [];
  if (!text && !files.length) return json({ error: "কিছু লেখা হয়নি" }, 400, env);
  if (text.length > MAX_TEXT) return json({ error: "বেশি বড় — ছোট করে লিখুন" }, 413, env);

  // ⚡ key থাকলে আগে দ্রুত লেন (৩–৮ সেকেন্ড), নইলে পুরনো Actions পথ
  if (fastReady(env)) {
    return await handleFastChat(env, ctx, payload);
  }

  const names = files.map((f) => f?.name).filter(Boolean);
  // 🧠 অ্যাপের নিজের চ্যাট-স্মৃতি (আগের কয়েক কথা) — এজেন্ট যেন প্রাসঙ্গিক উত্তর দেয়।
  //    Issue-এর পুরনো সব comment (হল) এখানে ইচ্ছে করে পাঠানো হয় না (`--no-hall`)।
  const past = (Array.isArray(payload?.history) ? payload.history : [])
    .filter((h) => h && typeof h.text === "string" && h.text.trim())
    .slice(-4)
    .map((h) => `- ${h.role === "assistant" ? "এজেন্ট" : "স্যার"}: ${h.text.replace(/\s+/g, " ").trim().slice(0, 240)}`);
  const memory = past.length ? `\n\n[আগের কথা]\n${past.join("\n")}` : "";
  // 🎯 স্যার যাদের বেছে নিয়েছেন (drop-down) — মার্কারে যায়, Actions শুধু তাদেরই ডাকে
  const targets = (Array.isArray(payload?.agents) ? payload.agents : [])
    .map((x) => String(x || "").trim().toLowerCase())
    .filter((x) => /^[a-z0-9_-]{1,24}$/.test(x))
    .slice(0, 8);
  const want = targets.length ? ` targets:${targets.join(",")}` : "";
  // 🏷️ মার্কারে mode থাকে — Actions রান এটা পড়ে direct/group ঠিক করে
  const tag = mode === "group" ? "group" : "agent";
  const body =
    `@mesh ${text}${names.length ? `\n\n📎 ${names.join(", ")}` : ""}` +
    `${memory}\n\n<!-- app:${Date.now()} mode:${tag}${want} -->`;

  return sse(env, async (send) => {
    send({ type: "status", text: "এজেন্টদের ডেকে পাঠাচ্ছি…" });
    const posted = await gh(env, issuePath(env, "/comments"), {
      method: "POST",
      body: JSON.stringify({ body }),
    });
    if (!posted.ok) {
      send({ type: "error", message: `GitHub: HTTP ${posted.status} — Issues: Write পারমিশন দেখুন` });
      return;
    }

    const since = new Date(Date.now() - 5000).toISOString();
    const startedAt = Date.now();
    // 🧪 টেস্টে ছোট করা যায় (POLL_MS / QUIET_MS env), ডিফল্ট আসল মান
    const pollMs = Number(env.POLL_MS) || 3000;
    const quietMs = Number(env.QUIET_MS) || 12000;
    const maxWait = Number(env.MAX_WAIT_MS) || DEFAULT_MAX_WAIT_MS;
    const maxPolls = Math.ceil(maxWait / pollMs) + 2;
    send({ type: "thinking", text: "ম্যানেজার কাজটা ভাগ করছে…" });
    send({ type: "tool", id: "mesh", name: "মেশ", input: "agent-mesh-router", state: "running" });

    const seen = new Set();
    let collected = "";
    let polls = 0;
    let firstAt = 0;
    let beatAt = Date.now();

    while (Date.now() - startedAt < maxWait && polls < maxPolls) {
      await sleep(pollMs);
      polls += 1;
      // প্রতি ২০ সেকেন্ডে হৃদস্পন্দন — অ্যাপে যেন "আটকে গেছে" মনে না হয়
      if (Date.now() - beatAt > 20000) {
        beatAt = Date.now();
        send({ type: "status", text: `এখনো কাজ চলছে… ${Math.round((Date.now() - startedAt) / 1000)} সেকেন্ড` });
      }
      const query = new URLSearchParams({ per_page: "40", since });
      const res = await gh(env, issuePath(env, `/comments?${query.toString()}`));
      if (!res.ok) { send({ type: "status", text: "GitHub-এ সমস্যা, আবার চেষ্টা…" }); continue; }

      const rows = (Array.isArray(res.data) ? res.data : []).filter((r) => isAgentComment(r) && !seen.has(r.id));
      if (!rows.length) {
        if (firstAt && Date.now() - firstAt > quietMs) break;
        continue;
      }

      for (const row of rows) {
        seen.add(row.id);
        const agent = agentOf(row);
        const agentText = cleanBody(row.body);
        if (!agentText) continue;
        agent.streamId = `m${row.id}`;

        if (mode === "group") {
          send({ type: "typing", agent });
          await sleep(120);
          await emitText(send, agentText, agent);
          send({ type: "agent_message", id: agent.streamId, agent, text: agentText });
        } else {
          const block = `### ${agent.emoji} ${agent.name}\n\n${agentText}\n\n`;
          collected += block;
          await emitText(send, block);
        }
        firstAt = firstAt || Date.now();
      }
      if (firstAt && Date.now() - firstAt > quietMs) break;
    }

    send({ type: "tool_result", id: "mesh", output: `${seen.size}টি উত্তর পাওয়া গেছে` });
    if (mode === "agent" && collected) send({ type: "final", text: collected });
    if (!seen.size) {
      send({ type: "error", message: "এজেন্টের উত্তর আসেনি — Actions রান দেখুন (.mesh-run / Issue)" });
    }
  });
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(env) });

    if (!url.pathname.startsWith("/api/")) {
      return json({ ok: true, service: "agent-team", hint: "এটা অ্যাপের সার্ভার" }, 200, env);
    }

    if (!authOk(request, env)) return json({ ok: false, error: "টোকেন ঠিক না" }, 401, env);

    try {
      if (url.pathname === "/api/health" && request.method === "GET") {
        return json(await handleHealth(env), 200, env);
      }
      if (url.pathname === "/api/agents" && request.method === "GET") {
        return json(handleAgents(), 200, env);
      }
      if (url.pathname === "/api/upload" && request.method === "POST") {
        const out = await handleUpload(request);
        return json(out.body, out.status, env);
      }
      if (url.pathname === "/api/chat" && request.method === "POST") {
        return await handleChat(request, env, ctx);
      }
      return json({ ok: false, error: "কোনো এমন ঠিকানা নেই" }, 404, env);
    } catch (err) {
      return json({ ok: false, error: `সার্ভারে সমস্যা: ${String(err).slice(0, 120)}` }, 500, env);
    }
  },
};

