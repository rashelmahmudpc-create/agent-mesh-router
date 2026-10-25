/**
 * 💾 সব কিছু ফোনের ভেতরেই জমা থাকে (localStorage) — কোনো সার্ভারে যায় না।
 * চ্যাট, সেটিংস, থিম — অ্যাপ বন্ধ করলেও থেকে যায়।
 */

const CHATS_KEY = "mesh.chats.v1";
const SETTINGS_KEY = "mesh.settings.v1";
const MAX_CHATS = 40;

export const defaultSettings = {
  apiBase: "",
  passcode: "",
  theme: "auto",
};

export function uid() {
  if (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  return `id-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
}

function readJson(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw);
    return parsed ?? fallback;
  } catch {
    return fallback;
  }
}

function writeJson(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false; // জায়গা শেষ / প্রাইভেট মোড — অ্যাপ তবু চলবে
  }
}

export function loadSettings() {
  const saved = readJson(SETTINGS_KEY, {});
  const merged = { ...defaultSettings, ...(saved && typeof saved === "object" ? saved : {}) };
  delete merged.mode; // পুরোনো সংস্করণের অবশিষ্ট থাকলে সরিয়ে দিই
  if (!["auto", "dark", "light"].includes(merged.theme)) merged.theme = "auto";
  return merged;
}

export function saveSettings(settings) {
  return writeJson(SETTINGS_KEY, settings);
}

export function loadChats() {
  const list = readJson(CHATS_KEY, []);
  if (!Array.isArray(list)) return [];
  return list
    .filter((chat) => chat && typeof chat === "object" && Array.isArray(chat.messages))
    .slice(0, MAX_CHATS);
}

export function saveChats(chats) {
  return writeJson(CHATS_KEY, chats.slice(0, MAX_CHATS));
}

export function newChat() {
  const now = Date.now();
  return {
    id: uid(),
    title: "নতুন চ্যাট",
    createdAt: now,
    updatedAt: now,
    cursor: 0, // লাইভ মোডে শেষ দেখা comment id
    since: "", // লাইভ মোডে "কখন থেকে" নতুন comment খুঁজবে
    messages: [],
  };
}

export function clearChats() {
  try {
    localStorage.removeItem(CHATS_KEY);
    return true;
  } catch {
    return false;
  }
}
