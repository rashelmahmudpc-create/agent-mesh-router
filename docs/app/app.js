/**
 * 🧠 মেশ চ্যাট — অ্যাপের মূল চলক (vanilla JS, কোনো ফ্রেমওয়ার্ক নেই)
 *
 * দুই মোড:
 *   🟢 লাইভ — সেটিংসে সার্ভার ঠিকানা দিলে আসল এজেন্টরা উত্তর দেয়
 *   🟡 ডেমো — কিছু না দিলে ভেতরের ছোট ব্রেইন উত্তর দেয় (ইন্টারনেট লাগে না)
 */

import { renderMarkdown, titleFrom } from "./js/md.js";
import { normalizeBase, isLive, health, sendChat, fetchReplies, demoReply } from "./js/api.js";
import * as store from "./js/store.js";

const $ = (id) => document.getElementById(id);

const el = {
  drawer: $("drawer"),
  scrim: $("scrim"),
  chatList: $("chatList"),
  thread: $("thread"),
  empty: $("empty"),
  input: $("input"),
  send: $("send"),
  composer: $("composer"),
  modeChip: $("modeChip"),
  hint: $("hint"),
  chatTitle: $("chatTitle"),
  statusPill: $("statusPill"),
  modeLine: $("modeLine"),
  toast: $("toast"),
  sheet: $("settingsSheet"),
  apiBase: $("apiBase"),
  passcode: $("passcode"),
  themeSeg: $("themeSeg"),
  settingsNote: $("settingsNote"),
};

let settings = store.loadSettings();
let chats = store.loadChats();
let activeId = chats.length ? chats[0].id : null;
let busy = false;
let typingNode = null;
let pollToken = 0;

/* ------------------------------------------------------------------ */
/* 🧰 ছোট সহায়ক                                                       */
/* ------------------------------------------------------------------ */

function currentChat() {
  return chats.find((chat) => chat.id === activeId) || null;
}

function persist() {
  store.saveChats(chats);
}

function toast(message, ms = 2600) {
  el.toast.textContent = message;
  el.toast.hidden = false;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => { el.toast.hidden = true; }, ms);
}

function timeLabel(ts) {
  try {
    return new Date(ts).toLocaleTimeString("bn-BD", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function nearBottom() {
  const gap = el.thread.scrollHeight - el.thread.scrollTop - el.thread.clientHeight;
  return gap < 130;
}

function scrollToBottom(force = false) {
  if (!force && !nearBottom()) return;
  el.thread.scrollTop = el.thread.scrollHeight;
}

function applyTheme() {
  document.documentElement.dataset.theme = settings.theme;
}

/* ------------------------------------------------------------------ */
/* 🎨 আঁকা                                                             */
/* ------------------------------------------------------------------ */

function renderChatList() {
  el.chatList.textContent = "";
  const sorted = [...chats].sort((a, b) => b.updatedAt - a.updatedAt);
  if (!sorted.length) {
    const p = document.createElement("p");
    p.className = "chat-list__empty";
    p.textContent = "এখনো কোনো চ্যাট নেই";
    el.chatList.appendChild(p);
    return;
  }
  for (const chat of sorted) {
    const row = document.createElement("div");
    row.className = `chat-item${chat.id === activeId ? " is-active" : ""}`;

    const open = document.createElement("button");
    open.type = "button";
    open.className = "chat-item__open";
    open.textContent = chat.title || "নতুন চ্যাট";
    open.addEventListener("click", () => { openChat(chat.id); closeDrawer(); });

    const del = document.createElement("button");
    del.type = "button";
    del.className = "chat-item__del";
    del.textContent = "🗑";
    del.setAttribute("aria-label", "চ্যাট মুছুন");
    del.addEventListener("click", (event) => {
      event.stopPropagation();
      removeChat(chat.id);
    });

    row.append(open, del);
    el.chatList.appendChild(row);
  }
}

function messageNode(message) {
  const article = document.createElement("article");
  article.className = `msg msg--${message.role}`;

  if (message.role === "user") {
    const bubble = document.createElement("div");
    bubble.className = "msg__bubble";
    bubble.textContent = message.text;
    article.appendChild(bubble);
    return article;
  }

  const avatar = document.createElement("div");
  avatar.className = "msg__avatar";
  avatar.textContent = message.emoji || "🤖";

  const body = document.createElement("div");
  body.className = "msg__body";

  const name = document.createElement("div");
  name.className = "msg__name";
  const who = document.createElement("b");
  who.textContent = message.agent || "এজেন্ট";
  const when = document.createElement("span");
  when.textContent = timeLabel(message.at);
  name.append(who, when);

  const text = document.createElement("div");
  text.className = "msg__text";
  if (message.pending) {
    text.innerHTML = '<span class="typing"><i></i><i></i><i></i></span>';
  } else if (message.failed) {
    text.textContent = message.text;
    text.classList.add("is-error");
  } else {
    text.innerHTML = renderMarkdown(message.text);
  }

  body.append(name, text);

  if (!message.pending && !message.failed) {
    const foot = document.createElement("div");
    foot.className = "msg__foot";
    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "mini-btn";
    copy.textContent = "📋 কপি";
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(message.text);
        toast("কপি হয়েছে ✅", 1400);
      } catch {
        toast("কপি করা গেল না");
      }
    });
    foot.appendChild(copy);
    body.appendChild(foot);
  }

  article.append(avatar, body);
  return article;
}

function renderThread() {
  const chat = currentChat();
  el.thread.querySelectorAll(".msg").forEach((node) => node.remove());
  typingNode = null;

  el.chatTitle.textContent = chat ? chat.title || "নতুন চ্যাট" : "নতুন চ্যাট";

  if (!chat || !chat.messages.length) {
    el.empty.hidden = false;
    return;
  }

  el.empty.hidden = true;
  for (const message of chat.messages) {
    el.thread.appendChild(messageNode(message));
  }
  scrollToBottom(true);
}

function showTyping(label = "এজেন্ট") {
  hideTyping();
  typingNode = messageNode({ role: "agent", agent: label, emoji: "🧠", pending: true, at: Date.now() });
  el.thread.appendChild(typingNode);
  scrollToBottom(true);
}

function hideTyping() {
  if (typingNode) {
    typingNode.remove();
    typingNode = null;
  }
}

function updateModeUI() {
  const live = isLive(settings);
  el.statusPill.textContent = live ? "🟢 লাইভ" : "🟡 ডেমো";
  el.statusPill.classList.toggle("pill--off", !live);
  el.modeLine.textContent = live
    ? "🟢 লাইভ — আসল এজেন্টরা উত্তর দেবে"
    : "🟡 ডেমো মোড — ইন্টারনেট ছাড়াই চলে";
  el.hint.textContent = live ? "উত্তর আসতে ১–২ মিনিট লাগতে পারে" : "ডেমো মোডে উত্তর নিজেই আসে";
  el.modeChip.textContent = live ? "👥 সবাই" : "🟡 ডেমো";
}

function renderAll() {
  applyTheme();
  updateModeUI();
  renderChatList();
  renderThread();
  el.send.disabled = !el.input.value.trim();
}


/* ------------------------------------------------------------------ */
/* 💬 চ্যাট খোলা / বানানো / মোছা                                       */
/* ------------------------------------------------------------------ */

function startNewChat() {
  if (!chats.length || currentChat()?.messages.length) {
    const chat = store.newChat();
    chats.unshift(chat);
    activeId = chat.id;
    persist();
  }
  renderAll();
  renderChatList();
  closeDrawer();
  el.input.focus();
}

function openChat(id) {
  activeId = id;
  renderChatList();
  renderThread();
}

function removeChat(id) {
  const chat = chats.find((item) => item.id === id);
  const question = chat && chat.messages.length ? "এই চ্যাটটা মুছে ফেলবেন?" : "মুছে ফেলবেন?";
  if (!window.confirm(question)) return;
  chats = chats.filter((item) => item.id !== id);
  if (activeId === id) activeId = chats.length ? chats[0].id : null;
  persist();
  renderAll();
}

/* ------------------------------------------------------------------ */
/* 📨 পাঠানো + উত্তরের অপেক্ষা                                         */
/* ------------------------------------------------------------------ */

function pushMessage(chat, message) {
  chat.messages.push(message);
  chat.updatedAt = Date.now();
  if (chat.title === "নতুন চ্যাট" && message.role === "user") {
    chat.title = titleFrom(message.text);
    el.chatTitle.textContent = chat.title;
  }
  persist();
}

function appendNode(message) {
  el.empty.hidden = true;
  el.thread.appendChild(messageNode(message));
}

async function send(text) {
  const body = text.trim();
  if (!body || busy) return;

  let chat = currentChat();
  if (!chat) {
    chat = store.newChat();
    chats.unshift(chat);
    activeId = chat.id;
  }

  pushMessage(chat, { role: "user", text: body, at: Date.now() });
  appendNode(chat.messages[chat.messages.length - 1]);
  renderChatList();

  el.input.value = "";
  autoGrow();
  el.send.disabled = true;
  scrollToBottom(true);

  busy = true;
  const live = isLive(settings);

  if (!live) {
    showTyping("ডেমো");
    const reply = await demoReply(body);
    hideTyping();
    const message = { role: "agent", agent: reply.agent, emoji: "🧠", text: reply.text, at: Date.now() };
    pushMessage(chat, message);
    appendNode(message);
    renderChatList();
    busy = false;
    scrollToBottom();
    return;
  }

  showTyping("এজেন্ট");
  // ⏱️ এখন থেকে নতুন comment গুলোই এই কথার উত্তর
  chat.since = new Date(Date.now() - 5000).toISOString();
  chat.cursor = 0;
  const started = await sendChat(settings, body);
  if (!started.ok) {
    hideTyping();
    const message = {
      role: "agent",
      agent: "সংযোগ ব্যর্থ",
      emoji: "⚠️",
      text: `${started.error}\n\nসেটিংসে সার্ভার ঠিকানা ও পাসকোড ঠিক আছে কি না দেখুন।`,
      at: Date.now(),
      failed: true,
    };
    pushMessage(chat, message);
    appendNode(message);
    busy = false;
    toast("পাঠানো গেল না ❌");
    return;
  }

  await waitForReplies(chat);
  hideTyping();
  busy = false;
  renderChatList();
  scrollToBottom();
}

/** লাইভ মোডে উত্তর খোঁজা — ২.৫ সেকেন্ড পর পর জিজ্ঞেস করে */
async function waitForReplies(chat) {
  const token = ++pollToken;
  const deadline = Date.now() + 5 * 60 * 1000; // সর্বোচ্চ ৫ মিনিট
  let firstReplyAt = 0;
  let quiet = 0;

  while (token === pollToken && Date.now() < deadline) {
    await sleep(firstReplyAt ? 2500 : 3000);
    if (token !== pollToken) return;

    const res = await fetchReplies(settings, { after: chat.cursor || 0, since: chat.since || "" });
    if (!res.ok) { quiet += 1; if (quiet >= 4) break; continue; }

    const incoming = Array.isArray(res.data?.messages) ? res.data.messages : [];
    if (!incoming.length) {
      if (firstReplyAt && Date.now() - firstReplyAt > 8000) break;
      continue;
    }

    for (const item of incoming) {
      chat.cursor = Math.max(chat.cursor || 0, Number(item.id) || 0);
      if (item.kind === "user") continue;
      pushMessage(chat, {
        role: "agent",
        agent: item.author || "এজেন্ট",
        emoji: item.emoji || "🤖",
        text: item.text || "(খালি উত্তর)",
        at: item.at || Date.now(),
      });
      appendNode(chat.messages[chat.messages.length - 1]);
    }
    firstReplyAt = firstReplyAt || Date.now();
    hideTyping();
    scrollToBottom();
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}


/* ------------------------------------------------------------------ */
/* ✍️ লেখার বাক্স                                                      */
/* ------------------------------------------------------------------ */

function autoGrow() {
  const input = el.input;
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 132)}px`;
}

/* ------------------------------------------------------------------ */
/* ☰ ড্রয়ার                                                           */
/* ------------------------------------------------------------------ */

function openDrawer() {
  el.drawer.classList.add("is-open");
  el.drawer.setAttribute("aria-hidden", "false");
  el.scrim.hidden = false;
}

function closeDrawer() {
  el.drawer.classList.remove("is-open");
  el.drawer.setAttribute("aria-hidden", "true");
  el.scrim.hidden = true;
}

/* ------------------------------------------------------------------ */
/* ⚙️ সেটিংস                                                          */
/* ------------------------------------------------------------------ */

function markThemeButtons() {
  el.themeSeg.querySelectorAll("button").forEach((btn) => {
    btn.classList.toggle("is-on", btn.dataset.theme === settings.theme);
  });
}

function isStandalone() {
  return (
    window.navigator.standalone === true ||
    window.matchMedia("(display-mode: standalone)").matches
  );
}

function openSettings() {
  el.apiBase.value = settings.apiBase || "";
  el.passcode.value = settings.passcode || "";
  el.settingsNote.textContent = isStandalone()
    ? "✅ হোম স্ক্রিন থেকে খুলেছে — অ্যাপের মতোই চলছে।"
    : "📱 iPhone-এ Share বাটন → Add to Home Screen দিলে অ্যাপ হয়ে যাবে।";
  markThemeButtons();
  closeDrawer();
  if (typeof el.sheet.showModal === "function") el.sheet.showModal();
  else el.sheet.setAttribute("open", "");
}

function closeSheet() {
  if (typeof el.sheet.close === "function") el.sheet.close();
  else el.sheet.removeAttribute("open");
}

function commitSettings({ close = true, quiet = false } = {}) {
  const base = normalizeBase(el.apiBase.value);
  if (el.apiBase.value.trim() && !/^https?:\/\/[^\s/]+\.[^\s]+/i.test(base)) {
    toast("সার্ভার ঠিকানাটা ঠিক না ⚠️");
    return false;
  }
  settings = { ...settings, apiBase: base, passcode: el.passcode.value.trim() };
  store.saveSettings(settings);
  renderAll();
  if (close) closeSheet();
  if (!quiet) toast(base ? "সেভ হয়েছে — লাইভ মোড 🟢" : "সেভ হয়েছে — ডেমো মোড 🟡");
  return true;
}

async function testConnection() {
  const base = normalizeBase(el.apiBase.value);
  if (!base) {
    el.settingsNote.textContent = "🟡 সার্ভার ঠিকানা খালি — ডেমো মোড চলছে।";
    return;
  }
  el.settingsNote.textContent = "⏳ পরীক্ষা চলছে…";
  const res = await health({ apiBase: base, passcode: el.passcode.value.trim() });
  if (res.ok) {
    const issue = res.data?.issue ? ` · Issue #${res.data.issue}` : "";
    el.settingsNote.textContent = `✅ সার্ভার ঠিক আছে${issue}`;
  } else {
    el.settingsNote.textContent = `❌ ${res.error}`;
  }
}


/* ------------------------------------------------------------------ */
/* 🔌 ইভেন্ট + চালু                                                    */
/* ------------------------------------------------------------------ */

function bindEvents() {
  el.composer.addEventListener("submit", (event) => {
    event.preventDefault();
    send(el.input.value);
  });

  el.input.addEventListener("input", () => {
    autoGrow();
    el.send.disabled = !el.input.value.trim() || busy;
  });

  el.input.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
    event.preventDefault();
    send(el.input.value);
  });

  $("menuBtn").addEventListener("click", openDrawer);
  $("drawerClose").addEventListener("click", closeDrawer);
  el.scrim.addEventListener("click", closeDrawer);
  $("newChat").addEventListener("click", startNewChat);
  $("newChatTop").addEventListener("click", startNewChat);
  $("openSettings").addEventListener("click", openSettings);

  el.modeChip.addEventListener("click", () => {
    toast(
      isLive(settings)
        ? "👥 লাইভ মোডে সব এজেন্ট একসাথে উত্তর দেয়"
        : "🟡 ডেমো — আসল এজেন্ট চাইলে সেটিংসে সার্ভার ঠিকানা দিন",
      2400,
    );
  });

  $("suggestions").addEventListener("click", (event) => {
    const btn = event.target.closest("[data-fill]");
    if (!btn) return;
    el.input.value = btn.dataset.fill;
    autoGrow();
    el.send.disabled = false;
    el.input.focus();
  });

  $("saveSettings").addEventListener("click", () => commitSettings());
  $("testConn").addEventListener("click", testConnection);
  el.themeSeg.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-theme]");
    if (!btn) return;
    settings = { ...settings, theme: btn.dataset.theme };
    store.saveSettings(settings);
    applyTheme();
    markThemeButtons();
  });

  $("clearChats").addEventListener("click", () => {
    if (!window.confirm("সব চ্যাট মুছে ফেলবেন? এটা আর ফেরানো যাবে না।")) return;
    store.clearChats();
    chats = [];
    activeId = null;
    renderAll();
    closeSheet();
    toast("সব চ্যাট মুছে ফেলা হয়েছে");
  });

  // 📱 কীবোর্ড নিচের বাক্স ঢেকে ফেললে লেখা দেখা যায়
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", () => scrollToBottom(true));
  }
}

function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;
  if (!/^https?:$/.test(location.protocol)) return;
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("./sw.js").catch(() => {});
  });
}

function boot() {
  applyTheme();
  bindEvents();
  renderAll();
  autoGrow();
  registerServiceWorker();

  if (!isStandalone() && !localStorage.getItem("mesh.installTip")) {
    setTimeout(() => {
      toast("📱 Share → Add to Home Screen দিলে অ্যাপ হয়ে যাবে", 4200);
      try { localStorage.setItem("mesh.installTip", "1"); } catch {}
    }, 2200);
  }

  window.addEventListener("online", () => toast("🟢 ইন্টারনেট ফিরে এসেছে", 1600));
  window.addEventListener("offline", () => toast("🟡 ইন্টারনেট নেই — অ্যাপ তবু চলবে", 2000));
}

boot();

