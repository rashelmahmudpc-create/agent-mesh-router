/**
 * 🧪 অ্যাপটা আসল DOM-এ চালিয়ে দেখা (jsdom) — ঐচ্ছিক পরীক্ষা।
 *
 *     npm install --no-save jsdom      # একবার
 *     node tests/js/dom_check.mjs
 *
 * jsdom না থাকলে চুপচাপ বাদ পড়ে (exit 0) — যাতে CI না ভাঙে।
 */
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "../..");
const WEB = path.join(ROOT, "docs", "app");

let JSDOM;
try {
  ({ JSDOM } = await import("jsdom"));
} catch {
  console.log("⏭️ jsdom নেই — DOM পরীক্ষা বাদ (ঐচ্ছিক). `npm i --no-save jsdom` দিয়ে চালান।");
  process.exit(0);
}

const dom = new JSDOM(fs.readFileSync(path.join(WEB, "index.html"), "utf8"), {
  url: "http://localhost/web/index.html",
  pretendToBeVisual: true,
  runScripts: "outside-only",
});
const { window } = dom;

const define = (name, value) =>
  Object.defineProperty(globalThis, name, { value, configurable: true, writable: true });

define("window", window);
define("document", window.document);
define("navigator", window.navigator);
define("localStorage", window.localStorage);
define("location", window.location);
define("HTMLElement", window.HTMLElement);
define("Element", window.Element);
define("Node", window.Node);
define("Event", window.Event);
define("CustomEvent", window.CustomEvent);
define("getComputedStyle", window.getComputedStyle.bind(window));

window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
window.confirm = () => true;

const errors = [];
window.addEventListener("error", (e) => errors.push(String(e.message)));

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const $ = (id) => window.document.getElementById(id);
let fails = 0;
const check = (label, ok, extra = "") => {
  console.log(`${ok ? "✔" : "✖"} ${label}${extra ? ` — ${extra}` : ""}`);
  if (!ok) fails += 1;
};

await import(path.join(WEB, "app.js"));

check("অ্যাপ লোড হয়েছে, খালি অবস্থা দেখা যাচ্ছে", $("empty") && !$("empty").hidden);
check("ডেমো ব্যাজ দেখাচ্ছে", $("statusPill").textContent.includes("ডেমো"));

$("suggestions")
  .querySelector("[data-fill]")
  .dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
check("সাজেশন চিপ ইনপুট ভরে", $("input").value.length > 5);

$("input").value = "আজকের কাজের অবস্থা বলো";
$("input").dispatchEvent(new window.Event("input", { bubbles: true }));
check("লেখা থাকলে পাঠানোর বাটন চালু", $("send").disabled === false);

$("composer").dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true }));
check("লেখার বাক্স খালি হয়েছে", $("input").value === "");
check("ইনপুট খালি হলে বাটন বন্ধ", $("send").disabled === true);
check("ইউজার মেসেজ দেখা যাচ্ছে", Boolean(window.document.querySelector(".msg--user")));
check("টাইপিং ইন্ডিকেটর চলছে", Boolean(window.document.querySelector(".typing")));

await wait(2600);

const agent = window.document.querySelector(".msg--agent");
check("এজেন্টের উত্তর এসেছে", Boolean(agent));
check("উত্তরে মার্কডাউন রেন্ডার হয়েছে (bold)", Boolean(agent?.querySelector("strong")));
check("টাইপিং ইন্ডিকেটর সরে গেছে", !window.document.querySelector(".typing"));
check("খালি অবস্থা লুকানো", $("empty").hidden === true);
check("শিরোনাম নিজে থেকে হয়েছে", $("chatTitle").textContent !== "নতুন চ্যাট");

const saved = JSON.parse(window.localStorage.getItem("mesh.chats.v1") || "[]");
check("চ্যাট ফোনে জমা হয়েছে", saved.length === 1 && saved[0].messages.length === 2);
check("উত্তরে কপি বাটন আছে", Boolean(agent?.querySelector(".mini-btn")));

$("menuBtn").dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
check("ড্রয়ার খোলে", $("drawer").classList.contains("is-open") && $("scrim").hidden === false);
$("scrim").dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
check("ড্রয়ার বন্ধ হয়", !$("drawer").classList.contains("is-open"));

$("openSettings").dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
check("সেটিংস খোলে", $("settingsSheet").hasAttribute("open"));
$("apiBase").value = "not a url";
$("saveSettings").dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
check("ভুল ঠিকানা আটকায়", !JSON.parse(window.localStorage.getItem("mesh.settings.v1") || "{}").apiBase);

$("apiBase").value = "mesh-chat.example.workers.dev";
$("passcode").value = "1234";
$("saveSettings").dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
const cfg = JSON.parse(window.localStorage.getItem("mesh.settings.v1") || "{}");
check("সার্ভার ঠিকানা সেভ হয় (https যোগ হয়)", cfg.apiBase === "https://mesh-chat.example.workers.dev");
check("লাইভ ব্যাজ দেখায়", $("statusPill").textContent.includes("লাইভ"));

$("newChatTop").dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
check("নতুন চ্যাট খোলে", $("empty").hidden === false && $("chatTitle").textContent === "নতুন চ্যাট");

check("কোনো JS এরর নেই", errors.length === 0, errors.join(" | "));

console.log(fails === 0 ? "\n✅ সব DOM পরীক্ষা পাস" : `\n❌ ${fails}টা ব্যর্থ`);
process.exit(fails === 0 ? 0 : 1);
