/**
 * 🔌 মেশ চ্যাট সার্ভার — Cloudflare Worker
 *
 * কাজ: অ্যাপ থেকে আসা কথা GitHub Issue-এ `@mesh ...` comment হিসেবে পাঠায়,
 *      আর এজেন্টদের উত্তর comment থেকে পড়ে অ্যাপকে ফিরিয়ে দেয়।
 *
 * 🔒 গোপন তথ্য: GitHub টোকেন এখানে (Worker env) থাকে — অ্যাপে কখনো যায় না।
 *
 * দরকারি env:
 *   GITHUB_TOKEN    → fine-grained PAT, শুধু Issues: Read & Write
 *   MESH_REPO       → "rashelmahmudpc-create/agent-mesh-router"
 *   MESH_ISSUE      → হলঘর Issue নম্বর (যেমন "3")
 *   APP_PASSCODE    → অ্যাপে যেটা লিখবেন (না দিলে যে কেউ ডাকতে পারবে)
 *   ALLOWED_ORIGIN  → ঐচ্ছিক, ডিফল্ট "*"
 */

const API = "https://api.github.com";
const MAX_TEXT = 4000;

const CORS = (env) => ({
  "access-control-allow-origin": env.ALLOWED_ORIGIN || "*",
  "access-control-allow-methods": "GET,POST,OPTIONS",
  "access-control-allow-headers": "content-type,x-passcode",
  "access-control-max-age": "86400",
});

const json = (data, status, env) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", ...CORS(env) },
  });

function safeEqual(a, b) {
  const left = String(a || "");
  const right = String(b || "");
  if (left.length !== right.length || !right) return false;
  let diff = 0;
  for (let i = 0; i < left.length; i += 1) diff |= left.charCodeAt(i) ^ right.charCodeAt(i);
  return diff === 0;
}

function authOk(request, env) {
  if (!env.APP_PASSCODE) return true; // পাসকোড না দিলে খোলা (শুধু নিজের ব্যবহারের জন্য)
  return safeEqual(request.headers.get("x-passcode"), env.APP_PASSCODE);
}

async function gh(env, path, init = {}) {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      authorization: `Bearer ${env.GITHUB_TOKEN}`,
      accept: "application/vnd.github+json",
      "user-agent": "mesh-chat-worker",
      "x-github-api-version": "2022-11-28",
      ...(init.body ? { "content-type": "application/json" } : {}),
    },
  });
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text }; }
  return { ok: res.ok, status: res.status, data };
}

function issuePath(env, suffix = "") {
  return `/repos/${env.MESH_REPO}/issues/${env.MESH_ISSUE}${suffix}`;
}

/** comment থেকে এজেন্টের নাম বের করা */
function agentOf(comment) {
  const marker = /<!--\s*mesh:([\w.-]+)\s*-->/.exec(comment.body || "");
  const name = marker ? marker[1] : comment.user?.login || "এজেন্ট";
  const emoji = { opencode: "🧑‍💻", claude: "🟠", hermes: "☤", cline: "🟦", openhands: "🖐️" }[name] || "🤖";
  return { name, emoji };
}

function cleanBody(body) {
  return String(body || "")
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/@mesh/g, "")
    .trim();
}

async function handleHealth(env) {
  if (!env.GITHUB_TOKEN || !env.MESH_REPO || !env.MESH_ISSUE) {
    return { ok: false, error: "Worker env ঠিক নেই (GITHUB_TOKEN / MESH_REPO / MESH_ISSUE)" };
  }
  const res = await gh(env, issuePath(env));
  if (!res.ok) return { ok: false, error: `GitHub: HTTP ${res.status}` };
  return { ok: true, repo: env.MESH_REPO, issue: Number(env.MESH_ISSUE), title: res.data?.title || "" };
}

async function handleChat(request, env) {
  let payload;
  try { payload = await request.json(); } catch { return { status: 400, body: { error: "JSON ঠিক নেই" } }; }

  const text = String(payload?.text || "").trim();
  if (!text) return { status: 400, body: { error: "কিছু লেখা হয়নি" } };
  if (text.length > MAX_TEXT) return { status: 413, body: { error: "বেশি বড় — ছোট করে লিখুন" } };

  // 🏛️ Issue-এ ডাক — mesh workflow এটাই পড়ে
  const body = `@mesh ${text}\n\n<!-- app:${Date.now()} -->`;

  const res = await gh(env, issuePath(env, "/comments"), {
    method: "POST",
    body: JSON.stringify({ body }),
  });
  if (!res.ok) return { status: 502, body: { error: `GitHub: HTTP ${res.status}` } };

  return { status: 200, body: { ok: true, id: Number(res.data?.id) || 0 } };
}

async function handleMessages(url, env) {
  const after = Number(url.searchParams.get("after") || 0);
  const since = url.searchParams.get("since") || "";
  const query = new URLSearchParams({ per_page: "100" });
  if (since) query.set("since", since);

  const res = await gh(env, issuePath(env, `/comments?${query.toString()}`));
  if (!res.ok) return { status: 502, body: { error: `GitHub: HTTP ${res.status}` } };

  const rows = Array.isArray(res.data) ? res.data : [];
  const messages = rows
    .filter((row) => Number(row.id) > after)
    .map((row) => {
      const isAgent = row.user?.type === "Bot" || /<!--\s*mesh:/.test(row.body || "");
      const { name, emoji } = agentOf(row);
      return {
        id: Number(row.id),
        kind: isAgent ? "agent" : "user",
        author: isAgent ? name : row.user?.login || "আপনি",
        emoji,
        text: cleanBody(row.body),
        at: Date.parse(row.created_at) || Date.now(),
      };
    })
    .filter((row) => row.text);

  return { status: 200, body: { ok: true, messages } };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS(env) });
    }

    if (!url.pathname.startsWith("/api/")) {
      return json({ ok: true, service: "mesh-chat", hint: "এটা অ্যাপের সার্ভার, ওয়েবসাইট নয়" }, 200, env);
    }

    if (!authOk(request, env)) return json({ ok: false, error: "পাসকোড ঠিক না" }, 401, env);

    try {
      if (url.pathname === "/api/health" && request.method === "GET") {
        return json(await handleHealth(env), 200, env);
      }

      if (url.pathname === "/api/chat" && request.method === "POST") {
        const out = await handleChat(request, env);
        return json(out.body, out.status, env);
      }

      if (url.pathname === "/api/messages" && request.method === "GET") {
        const out = await handleMessages(url, env);
        return json(out.body, out.status, env);
      }

      return json({ ok: false, error: "কোনো এমন ঠিকানা নেই" }, 404, env);
    } catch (err) {
      return json({ ok: false, error: `সার্ভারে সমস্যা: ${String(err).slice(0, 120)}` }, 500, env);
    }
  },
};

