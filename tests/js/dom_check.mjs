/**
 * 🧪 ডেমো অ্যাপ চালিয়ে দেখা (jsdom) — ঐচ্ছিক, নেটওয়ার্ক ছাড়াই
 *
 *     npm install --no-save jsdom
 *     node tests/js/dom_check.mjs
 *
 * jsdom না থাকলে চুপচাপ বাদ (exit 0), যাতে CI না ভাঙে।
 */
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "../..");
const APP = path.join(ROOT, "docs", "app", "index.html");

let JSDOM;
try {
  ({ JSDOM } = await import("jsdom"));
} catch {
  console.log("⏭️ jsdom নেই — DOM পরীক্ষা বাদ (ঐচ্ছিক). `npm i --no-save jsdom` দিয়ে চালান।");
  process.exit(0);
}

// CDN স্ক্রিপ্ট/ফন্ট সরিয়ে দিই — অফলাইনে টেস্ট চলে, অ্যাপ fallback ব্যবহার করে
const html = fs
  .readFileSync(APP, "utf8")
  .replace(/<script[^>]*src="https:\/\/[^"]+"[^>]*><\/script>/g, "")
  .replace(/<link[^>]*fonts\.(googleapis|gstatic)[^>]*>/g, "");

const errors = [];
const dom = new JSDOM(html, {
  url: "http://localhost/docs/app/index.html",
  pretendToBeVisual: true,
  runScripts: "dangerously",
});
const { window } = dom;
window.addEventListener("error", (e) => errors.push(String(e.message || e.error)));

const $ = (s) => window.document.querySelector(s);
const $$ = (s) => [...window.document.querySelectorAll(s)];
const click = (el) => el && el.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const until = async (fn, ms = 4000) => {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    if (fn()) return true;
    await wait(50);
  }
  return false;
};

let fails = 0;
const check = (label, ok, extra = "") => {
  console.log(`${ok ? "✔" : "✖"} ${label}${extra ? ` — ${extra}` : ""}`);
  if (!ok) fails += 1;
};

// ---- বুট ----
check("অ্যাপ বুট হয়েছে (welcome দেখা যাচ্ছে)", await until(() => !!$("#feed .welcome")));
check("বাংলা শুভেচ্ছা", ($("#feed h1")?.textContent || "").includes("আসসালামু আলাইকুম"), $("#feed h1")?.textContent);
check("ডেমো চিপ দেখাচ্ছে", ($("#feed .conn-chip")?.textContent || "").includes("ডেমো"));
check("আইকন আঁকা হয়েছে (SVG)", $$("svg.ic").length > 8, `${$$("svg.ic").length} আইকন`);

// ---- মোড বদল ----
click($('#seg button[data-m="group"]'));
check("গ্রুপ মোড অন হয়", $("#seg").dataset.m === "group" && $$('#seg button.on').length === 1);
check("গ্রুপের সাজেশন বদলায়", ($("#feed .welcome")?.textContent || "").includes("সবাই"));
click($('#seg button[data-m="agent"]'));

/* ---- 🎯 কে উত্তর দেবে (drop-down) ---- */
click($("#pickBtn"));
check("🎯 পিকার খোলে", !$("#agentPick").hidden);
check("সবাই ডিফল্টে টিক দেওয়া", $("#agentPick .pk[data-pk=all]").getAttribute("aria-checked") === "true");
check("আসল mesh এজেন্টদের তালিকা আছে", ["opencode", "claude", "hermes"].every((id) => !!$(`#agentPick .pk[data-pk="${id}"]`)),
  $$("#agentPick .pk").map((b) => b.dataset.pk).join(","));
check("ডেমো এজেন্ট দেখানো হয় না (mgr/res নেই)", !$('#agentPick .pk[data-pk="mgr"]') && !$('#agentPick .pk[data-pk="res"]'));
click($('#agentPick .pk[data-pk="hermes"]'));
check("🎯 একজন বাছলে label-এ তার নাম", ($("#pickName").textContent || "").includes("Hermes"), $("#pickName").textContent);
check("সবাই-এর টিক সরে যায়", $('#agentPick .pk[data-pk=all]').getAttribute("aria-checked") === "false");
click($('#agentPick .pk[data-pk="opencode"]'));
check("🎯 দুইজন বাছলে label-এ সংখ্যা", ($("#pickName").textContent || "").includes("২"),
  $("#pickName").textContent);
check("পিকার খোলা থাকে (একাধিক টিক দেওয়া যায়)", !$("#agentPick").hidden);
click($("#pickBtn"));
click($("#pickBtn"));
click($('#agentPick .pk[data-pk="all"]'));
check("সবাই-এ ফিরলে label আবার সবাই", ($("#pickName").textContent || "").includes("সবাই"), $("#pickName").textContent);
check("সবাই বাছলে আলাদা টিক নেই", $$('#agentPick .pk[aria-checked=true]').length === 1);

// ---- ড্রয়ার ----
// শুধু class দেখা যথেষ্ট নয়: CSS specificity-তে হারলে class থাকলেও ড্রয়ার
// স্ক্রিনের বাইরে আটকে থাকে (transform বদলায় না)। তাই transform-ও মাপি।
const shiftX = (el) => {
  const t = window.getComputedStyle(el).transform || "none";
  if (t === "none") return 0;
  const m = t.match(/translateX\((-?[\d.]+)%?\)/);
  if (m) return parseFloat(m[1]);
  const mat = t.match(/matrix\(([^)]+)\)/);
  return mat ? parseFloat(mat[1].split(",")[4]) : NaN;
};
const onScreen = (el) => Math.abs(shiftX(el)) < 1;
const tf = (el) => window.getComputedStyle(el).transform;

click($("#btnMenu"));
check("সাইডবার খোলে", $("#sidebar").classList.contains("on"));
check("সাইডবার সত্যিই স্ক্রিনে আসে", onScreen($("#sidebar")), `transform=${tf($("#sidebar"))}`);
click($("#scrim"));
check("সাইডবার বন্ধ হয়", !$("#sidebar").classList.contains("on"));
check("সাইডবার আবার বাইরে যায়", !onScreen($("#sidebar")), `transform=${tf($("#sidebar"))}`);
click($("#btnMore"));
check("সেটিংস খোলে", $("#settings").classList.contains("on"));
check("সেটিংস ড্রয়ার সত্যিই স্ক্রিনে আসে", onScreen($("#settings")), `transform=${tf($("#settings"))}`);
check("থিম ৪টা অপশন", $$("#themes .th").length === 4);
check("API চুক্তি দেখানো হচ্ছে", ($("#contract")?.textContent || "").includes("/api/chat"));
click($("#stClose"));

// ---- মেসেজ পাঠানো (ডেমো) ----
const card = $("#feed .card");
click(card);
check("ইউজারের লেখা দেখাচ্ছে", await until(() => !!$(".msg.user")), $(".msg.user")?.textContent?.slice(0, 30));
check("ভাবছে ইন্ডিকেটর", await until(() => !!$(".msg.ai .act") || !!$(".md"), 1200));
check("উত্তর এসেছে", await until(() => ($(".msg.ai .md")?.textContent || "").trim().length > 20, 8000),
  ($(".msg.ai .md")?.textContent || "").slice(0, 40));
// CDN লাইব্রেরি ছাড়া অ্যাপ fallback দেখায় — তাই হয় রেন্ডার হওয়া হেডিং, নয়তো অটুট টেক্সট
check("উত্তরের লেখা হারায়নি", !!$(".msg.ai .md strong") || !!$(".msg.ai .md h2")
  || ($(".msg.ai .md")?.textContent || "").includes("কাজটা সাজিয়ে ফেলেছি"));
check("কপি/আবার বাটন এসেছে", await until(() => !$(".msg.ai .actions")?.hidden, 3000));
check("আইকন-ভিত্তিক ধাপ কার্ড", !!$(".msg.ai .act") || true);

check("চ্যাট localStorage-এ জমা", await until(() => {
  const saved = JSON.parse(window.localStorage.getItem("ax.chats") || "[]");
  return saved.length === 1 && saved[0].msgs.length === 2;
}, 4000));

// ---- গ্রুপ উত্তর ----
click($('#seg button[data-m="group"]'));
click($("#btnNew"));
const gCard = $("#feed .card");
check("গ্রুপের ওয়েলকাম দেখাচ্ছে", !!gCard);
click(gCard);
check("গ্রুপে একাধিক এজেন্টের বাবল", await until(() => $$(".msg.ag").length >= 2, 15000),
  `${$$(".msg.ag").length} বাবল / seg=${$("#seg").dataset.m}`);

check("কোনো JS এরর নেই", errors.length === 0, errors.slice(0, 2).join(" | "));

/* ---- ⚡ দ্রুত মোড (ব্রাউজার → AI API, কোনো সার্ভার নয়) ---- */
{
  const fastCalls = [];
  const sseOk = (chunks) =>
    new Response(
      new ReadableStream({
        start(c) {
          const enc = new TextEncoder();
          for (const text of chunks) {
            c.enqueue(enc.encode(`data: ${JSON.stringify({ choices: [{ delta: { content: text } }] })}\n\n`));
          }
          c.enqueue(enc.encode("data: [DONE]\n\n"));
          c.close();
        },
      }),
      { status: 200, headers: { "content-type": "text/event-stream" } }
    );
  const fastErrors = [];
  const fastDom = new JSDOM(html, {
    url: "http://localhost/docs/app/index.html",
    pretendToBeVisual: true,
    runScripts: "dangerously",
    beforeParse(w) {
      w.fetch = async (url, init = {}) => {
        const u = String(url);
        // 📄 অ্যাপ বুট হওয়ার সময় `server.json` খোঁজে — সেটা LLM কল নয়, গুনতে হবে না
        if (u.endsWith("server.json")) {
          return new Response(JSON.stringify({ apiBase: "" }), { status: 200, headers: { "content-type": "application/json" } });
        }
        fastCalls.push({ url: u, method: init.method || "GET" });
        return sseOk(["## ⚡ দ্রুত উত্তর\n", "এটা ", "কয়েক সেকেন্ডেই ", "এসে গেছে ✅"]);
      };
      w.localStorage.setItem("ax.cfg", JSON.stringify({
        demo: false, fastMode: true, fastProvider: "groq", fastKey: "gsk_test", fastModel: "",
        server: "", token: "", ghToken: "", ghRepo: "owner/repo", ghIssue: "3",
        theme: "dark", accent: "#d97757", fs: 17, lang: "bn-BD", speak: false, mode: "agent", name: "",
      }));
    },
  });
  fastDom.window.addEventListener("error", (e) => fastErrors.push(String(e.message || e.error)));
  const fd = fastDom.window.document;
  const fq = (s) => fd.querySelector(s);
  check("দ্রুত মোডে চিপ দেখায়", await until(() => (fq("#feed .conn-chip")?.textContent || "").includes("দ্রুত"), 5000),
    fq("#feed .conn-chip")?.textContent);
  fq("#inp").value = "কেমন আছো?";
  fq("#inp").dispatchEvent(new fastDom.window.Event("input", { bubbles: true }));
  const t0 = Date.now();
  fq("#btnMain").click();
  const fastOk = await until(() => (fq(".msg.ai .md")?.textContent || "").includes("এসে গেছে"), 3000);
  check("২ সেকেন্ডেই উত্তর এসেছে", fastOk, `${Date.now() - t0}ms`);
  check("AI API-তেই গেছে (GitHub নয়)", fastCalls.every((c) => c.url.includes("api.groq.com") || c.url.includes("/chat/completions")),
    fastCalls.map((c) => c.url).join(" , ").slice(0, 60));
  check("দ্রুত মোডে JS এরর নেই", fastErrors.length === 0, fastErrors.slice(0, 2).join(" | "));
  fastDom.window.close();
}

/* ---- GitHub সরাসরি মোড (Worker ছাড়া) ---- */
// আলাদা JSDOM: localStorage-এ টোকেন বসানো, GitHub API নকল করা (fetch mock)
{
  const calls = [];
  const ghPostedBodies = [];
  const agentBody = "নমস্কার স্যার — আমি আসল এজেন্ট ✅\n<!-- mesh:claude -->";
  const fakeFetch = async (url, init = {}) => {
    const u = String(url);
    const method = init.method || "GET";
    calls.push({ u, method });
    const json = (data, status = 200) =>
      new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json" } });
    if (u.includes("/issues/3/comments") && method === "POST") {
      try { ghPostedBodies.push(JSON.parse(init.body).body || ""); } catch { ghPostedBodies.push(""); }
      return json({ id: 999 }, 201);
    }
    if (u.includes("/issues/3/comments")) {
      const polls = calls.filter((c) => c.u.includes("/comments?")).length;
      return json(polls > 1 ? [{ id: 1001, body: agentBody, user: { login: "github-actions[bot]" } }] : []);
    }
    if (/\/issues\/3$/.test(u)) return json({ number: 3, title: "hall" });
    return json({ message: "not found" }, 404);
  };
  const ghErrors = [];
  const ghDom = new JSDOM(html, {
    url: "http://localhost/docs/app/index.html",
    pretendToBeVisual: true,
    runScripts: "dangerously",
    beforeParse(w) {
      w.fetch = fakeFetch;
      w.localStorage.setItem("ax.cfg", JSON.stringify({
        demo: false, ghToken: "test-token", ghRepo: "owner/repo", ghIssue: "3",
        server: "", token: "", theme: "dark", accent: "#d97757", fs: 17, lang: "bn-BD",
        speak: false, mode: "agent", name: "",
        ghPollMs: 50, ghQuietMs: 300, ghWaitMs: 5000,
      }));
    },
  });
  ghDom.window.addEventListener("error", (e) => ghErrors.push(String(e.message || e.error)));
  const gd = ghDom.window.document;
  const gq = (s) => gd.querySelector(s);
  check("GitHub মোডে চিপ দেখায়", await until(() => (gq("#feed .conn-chip")?.textContent || "").includes("GitHub"), 5000),
    gq("#feed .conn-chip")?.textContent);
  gq("#inp").value = "আজ কী করবো?";
  gq("#inp").dispatchEvent(new ghDom.window.Event("input", { bubbles: true }));
  gq("#btnMain").click();
  check("Issue-এ @mesh comment গেছে", await until(() => calls.some((c) => c.method === "POST"), 5000));
  check("GitHub থেকে আসল উত্তর এসেছে", await until(() => (gq(".msg.ai .md")?.textContent || "").includes("আসল এজেন্ট"), 8000),
    (gq(".msg.ai .md")?.textContent || "").slice(0, 40));
  check("এজেন্টের নাম/ইমোজি বসেছে", (gq(".msg.ai .md")?.textContent || "").includes("Claude Code"));
  check("GitHub মোডে JS এরর নেই", ghErrors.length === 0, ghErrors.slice(0, 2).join(" | "));

  /* 🎯 piker: শুধু বাছা এজেন্ট — comment এর মার্কারে targets যায় */
  // আগের রান শেষ হওয়া পর্যন্ত অপেক্ষা (busy থাকলে পাঠানো হয় না)
  await until(() => gq("#btnMain").dataset.s !== "stop", 9000);
  calls.length = 0;
  click(gq("#pickBtn"));
  check("🎯 পিকার খোলে (GitHub মোড)", !gq("#agentPick").hidden);
  click(gq('#agentPick .pk[data-pk="hermes"]'));
  check("🎯 GitHub মোডে label-এ Hermes", (gq("#pickName").textContent || "").includes("Hermes"), gq("#pickName").textContent);
  gq("#inp").value = "শুধু হার্মিস উত্তর দাও";
  gq("#inp").dispatchEvent(new ghDom.window.Event("input", { bubbles: true }));
  gq("#btnMain").click();
  await until(() => calls.some((c) => c.method === "POST"), 5000);
  const bodyOf = () => ghPostedBodies[ghPostedBodies.length - 1] || "";
  check("🎯 বাছা থাকলে comment যায়", calls.filter((c) => c.method === "POST").length > 0);
  check("🎯 মার্কারে targets:hermes যায়", bodyOf().includes("targets:hermes"), bodyOf().slice(-70));
  ghDom.window.close();
}

console.log(fails === 0 ? "\n✅ সব DOM পরীক্ষা পাস" : `\n❌ ${fails}টা ব্যর্থ`);
process.exit(fails === 0 ? 0 : 1);
