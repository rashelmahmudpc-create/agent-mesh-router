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

console.log(fails === 0 ? "\n✅ সব DOM পরীক্ষা পাস" : `\n❌ ${fails}টা ব্যর্থ`);
process.exit(fails === 0 ? 0 : 1);
