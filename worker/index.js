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
  if (!env.GITHUB_TOKEN || !env.MESH_REPO || !env.MESH_ISSUE) {
    return { ok: false, error: "Worker env ঠিক নেই (GITHUB_TOKEN / MESH_REPO / MESH_ISSUE)" };
  }
  const res = await gh(env, issuePath(env));
  if (!res.ok) return { ok: false, error: `GitHub: HTTP ${res.status}` };
  return { ok: true, repo: env.MESH_REPO, issue: Number(env.MESH_ISSUE), title: res.data?.title || "" };
}

function handleAgents() {
  const ids = ["opencode", "claude", "hermes"];
  return ids.map((id) => ({
    id,
    name: id.charAt(0).toUpperCase() + id.slice(1),
    role: ROLE[id],
    emoji: EMOJI[id],
    color: COLOR[id],
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


async function handleChat(request, env) {
  let payload;
  try { payload = await request.json(); } catch { return json({ error: "JSON ঠিক নেই" }, 400, env); }

  const text = String(payload?.message || "").trim();
  const mode = payload?.mode === "group" ? "group" : "agent";
  const files = Array.isArray(payload?.attachments) ? payload.attachments : [];
  if (!text && !files.length) return json({ error: "কিছু লেখা হয়নি" }, 400, env);
  if (text.length > MAX_TEXT) return json({ error: "বেশি বড় — ছোট করে লিখুন" }, 413, env);

  const names = files.map((f) => f?.name).filter(Boolean);
  const body = `@mesh ${text}${names.length ? `\n\n📎 ${names.join(", ")}` : ""}\n\n<!-- app:${Date.now()} -->`;

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
  async fetch(request, env) {
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
        return await handleChat(request, env);
      }
      return json({ ok: false, error: "কোনো এমন ঠিকানা নেই" }, 404, env);
    } catch (err) {
      return json({ ok: false, error: `সার্ভারে সমস্যা: ${String(err).slice(0, 120)}` }, 500, env);
    }
  },
};

