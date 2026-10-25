/**
 * 🧪 Worker পরীক্ষা — নকল GitHub দিয়ে, আসল টোকেন ছাড়াই।
 *
 *     node tests/js/worker_check.mjs
 *
 * সফল হলে exit 0, নইলে 1 (CI-তে ব্যবহার করা যায়)।
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "../..");
const source = fs.readFileSync(path.join(ROOT, "worker/index.js"), "utf8");

// Worker ESM — অস্থায়ী .mjs বানিয়ে চালাই (রিপোতে অপ্রয়োজনীয় ফাইল রাখি না)
const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "mesh-worker-"));
const tmpFile = path.join(tmpDir, "worker.mjs");
fs.writeFileSync(tmpFile, source);

const calls = [];
globalThis.fetch = async (url, init = {}) => {
  calls.push({ url: String(url), init });
  const u = String(url);
  const reply = (data, status = 200) =>
    new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json" } });

  if (u.endsWith("/comments") && init.method === "POST") {
    return reply({ id: 999, body: JSON.parse(init.body).body }, 201);
  }
  if (u.includes("/comments?")) {
    return reply([
      { id: 100, body: "পুরোনো কথা", user: { login: "rashel", type: "User" }, created_at: "2026-10-25T10:00:00Z" },
      { id: 101, body: "<!-- mesh:opencode -->\nহ্যালো স্যার ✅", user: { login: "github-actions[bot]", type: "Bot" }, created_at: "2026-10-25T10:01:00Z" },
      { id: 102, body: "<!-- mesh:claude -->\n```js\nconst a = 1;\n```", user: { login: "github-actions[bot]", type: "Bot" }, created_at: "2026-10-25T10:02:00Z" },
    ]);
  }
  if (/\/issues\/\d+$/.test(u)) return reply({ number: 3, title: "hall" });
  return reply({ message: "not found" }, 404);
};

const { default: worker } = await import(tmpFile);

const env = {
  GITHUB_TOKEN: "test-token",
  MESH_REPO: "owner/repo",
  MESH_ISSUE: "3",
  APP_PASSCODE: "1234",
  ALLOWED_ORIGIN: "*",
};

const req = (p, opts = {}) => new Request(`https://w.dev${p}`, opts);
let fails = 0;
const check = (label, ok, extra = "") => {
  console.log(`${ok ? "✔" : "✖"} ${label}${extra ? ` — ${extra}` : ""}`);
  if (!ok) fails += 1;
};

let res = await worker.fetch(req("/api/chat", { method: "OPTIONS" }), env);
check("OPTIONS → 204 + CORS", res.status === 204 && res.headers.get("access-control-allow-origin") === "*");

res = await worker.fetch(req("/api/chat", { method: "POST", headers: { "x-passcode": "0000" }, body: "{}" }), env);
check("ভুল পাসকোড → 401", res.status === 401);

res = await worker.fetch(req("/api/health", { headers: { "x-passcode": "1234" } }), env);
const health = await res.json();
check("health ঠিক আছে", res.status === 200 && health.ok && health.issue === 3);

res = await worker.fetch(
  req("/api/chat", {
    method: "POST",
    headers: { "x-passcode": "1234", "content-type": "application/json" },
    body: JSON.stringify({ text: "আজ কী করবো?" }),
  }),
  env,
);
const chat = await res.json();
const posted = calls.filter((c) => c.init.method === "POST").pop();
const postedBody = posted ? JSON.parse(posted.init.body).body : "";
check("কথা পাঠানো গেল", res.status === 200 && chat.ok && chat.id === 999);
check("Issue-এ @mesh গেছে", postedBody.startsWith("@mesh আজ কী করবো?"));

res = await worker.fetch(
  req("/api/chat", { method: "POST", headers: { "x-passcode": "1234" }, body: JSON.stringify({ text: "  " }) }),
  env,
);
check("খালি লেখা → 400", res.status === 400);

res = await worker.fetch(
  req("/api/messages?after=100&since=2026-10-25T09:59:00Z", { headers: { "x-passcode": "1234" } }),
  env,
);
const msgs = await res.json();
check("পুরোনো comment বাদ পড়ে", msgs.messages.length === 2);
check("এজেন্টের নাম বের হয়", msgs.messages[0].author === "opencode" && msgs.messages[0].emoji === "🧑‍💻");
check("মার্কার লেখা থেকে মোছে", !msgs.messages[0].text.includes("<!--"));
check("কোড ব্লক অটুট", msgs.messages[1].text.includes("```js"));
check("সবই agent হিসেবে চিহ্নিত", msgs.messages.every((m) => m.kind === "agent"));

res = await worker.fetch(req("/api/nope", { headers: { "x-passcode": "1234" } }), env);
check("অজানা ঠিকানা → 404", res.status === 404);

res = await worker.fetch(req("/api/health"), { ...env, APP_PASSCODE: "" });
check("পাসকোড না দিলে খোলা", res.status === 200);

fs.rmSync(tmpDir, { recursive: true, force: true });

console.log(fails === 0 ? "\n✅ Worker সব পরীক্ষায় পাস" : `\n❌ ${fails}টা ব্যর্থ`);
process.exit(fails === 0 ? 0 : 1);
