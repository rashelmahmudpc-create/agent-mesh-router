/**
 * 🧪 Worker পরীক্ষা — চুক্তি অনুযায়ী আচরণ, নকল GitHub দিয়ে (আসল টোকেন ছাড়াই)
 *
 *     node tests/js/worker_check.mjs
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "../..");
const source = fs.readFileSync(path.join(ROOT, "worker/index.js"), "utf8");

const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "agent-team-"));
const tmpFile = path.join(tmpDir, "worker.mjs");
fs.writeFileSync(tmpFile, source);

const calls = [];
let commentRows = [];

globalThis.fetch = async (url, init = {}) => {
  calls.push({ url: String(url), init });
  const u = String(url);
  const reply = (data, status = 200) =>
    new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json" } });

  if (u.endsWith("/comments") && init.method === "POST") {
    commentRows = [
      { id: 501, body: "<!-- mesh:opencode -->\nহ্যালো স্যার ✅", user: { login: "github-actions[bot]", type: "Bot" }, created_at: new Date().toISOString() },
      { id: 502, body: "<!-- mesh:claude -->\n## প্ল্যান\n\n- এক\n- দুই", user: { login: "github-actions[bot]", type: "Bot" }, created_at: new Date().toISOString() },
    ];
    return reply({ id: 500 }, 201);
  }
  if (u.includes("/comments?")) {
    // প্রথম পোলে কিছু নেই, পরে উত্তর আসে — বাস্তবের মতো
    const polled = calls.filter((c) => c.url.includes("/comments?")).length;
    return reply(polled > 1 ? commentRows : []);
  }
  if (/\/issues\/\d+$/.test(u)) return reply({ number: 3, title: "hall" });
  return reply({ message: "not found" }, 404);
};

const { default: worker } = await import(tmpFile);

const env = {
  GITHUB_TOKEN: "test-token",
  MESH_REPO: "owner/repo",
  MESH_ISSUE: "3",
  APP_TOKEN: "secret123",
  ALLOWED_ORIGIN: "*",
  POLL_MS: "10",
  QUIET_MS: "60",
  MAX_WAIT_MS: "2000", // টেস্ট আটকে না থাকে; আসল ডিফল্ট ৫ মিনিট (worker/index.js)
};

const req = (p, opts = {}) => new Request(`https://w.dev${p}`, opts);
let fails = 0;
const check = (label, ok, extra = "") => {
  console.log(`${ok ? "✔" : "✖"} ${label}${extra ? ` — ${extra}` : ""}`);
  if (!ok) fails += 1;
};

/** SSE বডি পড়ে ইভেন্টের তালিকা */
async function eventsOf(response) {
  const text = await response.text();
  return text
    .split("\n")
    .filter((l) => l.startsWith("data:"))
    .map((l) => JSON.parse(l.slice(5).trim()));
}

let res = await worker.fetch(req("/api/chat", { method: "OPTIONS" }), env);
check("OPTIONS → 204 + CORS", res.status === 204 && res.headers.get("access-control-allow-origin") === "*");

res = await worker.fetch(req("/api/health"), env);
check("টোকেন ছাড়া → 401", res.status === 401);

res = await worker.fetch(req("/api/health", { headers: { authorization: "Bearer wrong" } }), env);
check("ভুল টোকেন → 401", res.status === 401);

const auth = { authorization: "Bearer secret123" };

res = await worker.fetch(req("/api/health", { headers: auth }), env);
const health = await res.json();
check("health ঠিক আছে", res.status === 200 && health.ok && health.issue === 3);

res = await worker.fetch(req("/api/agents", { headers: auth }), env);
const agents = await res.json();
check("agents: ৩ জন, চুক্তি অনুযায়ী ফিল্ড", Array.isArray(agents) && agents.length === 3
  && agents.every((a) => a.id && a.name && a.role && a.emoji && a.color), agents.map((a) => a.id).join(","));

res = await worker.fetch(req("/api/nope", { headers: auth }), env);
check("অজানা ঠিকানা → 404", res.status === 404);

/* ---- আপলোড ---- */
const form = new FormData();
form.append("file", new Blob(["hello"], { type: "text/plain" }), "note.txt");
res = await worker.fetch(req("/api/upload", { method: "POST", headers: auth, body: form }), env);
const up = await res.json();
check("upload নাম-টাইপ ফেরায়", res.status === 200 && up.name === "note.txt" && up.type === "text/plain");

/* ---- চ্যাট (agent মোড, SSE) ---- */
const chatReq = (body, headers = auth) =>
  worker.fetch(req("/api/chat", { method: "POST", headers: { ...headers, "content-type": "application/json" }, body: JSON.stringify(body) }), env);

res = await chatReq({ chat_id: "c1", mode: "agent", message: "আজ কী করবো?" });
check("chat → text/event-stream", (res.headers.get("content-type") || "").includes("text/event-stream"));
const posted = calls.filter((c) => c.init.method === "POST" && c.url.endsWith("/comments")).pop();
const postedBody = posted ? JSON.parse(posted.init.body).body : "";
const evs = await eventsOf(res);
check("Issue-এ @mesh comment গেছে", postedBody.startsWith("@mesh আজ কী করবো?"), postedBody.split("\n")[0]);
check("status ইভেন্ট আছে", evs.some((e) => e.type === "status"));
check("tool ইভেন্ট আছে", evs.some((e) => e.type === "tool" && e.name === "মেশ"));
check("delta স্ট্রিম হয়েছে", evs.filter((e) => e.type === "delta").length > 2, `${evs.filter((e) => e.type === "delta").length} টুকরা`);
const deltaAll = evs.filter((e) => e.type === "delta").map((e) => e.text).join("");
check("দুই এজেন্টের লেখা এসেছে", /opencode/i.test(deltaAll) && deltaAll.includes("প্ল্যান"), deltaAll.slice(0, 40));
check("tool_result শেষে", evs.filter((e) => e.type === "tool_result").length === 1);

/* ---- চ্যাট (group মোড) ---- */
const before = calls.length;
res = await chatReq({ chat_id: "c2", mode: "group", message: "সবাই পরিচয় দাও" });
const gev = await eventsOf(res);
check("group: typing ইভেন্ট", gev.some((e) => e.type === "typing" && e.agent?.id === "opencode"));
check("group: agent_message আছে", gev.filter((e) => e.type === "agent_message").length > 2);
check("group: delta জোড়া লাগলে পুরো লেখা হয়", (() => {
  const joined = {};
  for (const e of gev.filter((x) => x.type === "agent_message")) joined[e.id] = (joined[e.id] || "") + (e.delta || "");
  return Object.values(joined).some((t) => t.includes("হ্যালো স্যার"));
})());
check("group: নতুন comment পোস্ট হয়েছে", calls.length > before);

/* ---- খালি লেখা ---- */
res = await chatReq({ message: "   " });
check("খালি লেখা → 400", res.status === 400);

fs.rmSync(tmpDir, { recursive: true, force: true });

console.log(fails === 0 ? "\n✅ Worker সব পরীক্ষায় পাস" : `\n❌ ${fails}টা ব্যর্থ`);
process.exit(fails === 0 ? 0 : 1);
