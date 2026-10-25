/**
 * 📝 ছোট মার্কডাউন রেন্ডারার — নিরাপদ, কোনো লাইব্রেরি ছাড়া।
 * আগে সব HTML escape হয়, তারপর অল্প কিছু ফরম্যাট যোগ হয়।
 * তাই এজেন্টের লেখায় <script> থাকলেও সেটা কখনো চলে না।
 */

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ESCAPES[ch]);
}

export function renderMarkdown(source) {
  const raw = String(source ?? "").replace(/\u0000/g, "");
  const vault = [];
  const stash = (html) => `\u0000${vault.push(html) - 1}\u0000`;

  // ১) কোড ব্লক আগে সরিয়ে রাখি — ভেতরের লেখায় ফরম্যাট চলবে না
  let text = raw.replace(/```([\w+#.-]*)\n?([\s\S]*?)```/g, (_m, lang, code) => {
    const cls = lang ? ` class="language-${escapeHtml(lang)}"` : "";
    return stash(`<pre><code${cls}>${escapeHtml(code.replace(/\n+$/, ""))}</code></pre>`);
  });

  // ২) বাকি সব escape
  text = escapeHtml(text);

  // ৩) ইনলাইন কোড
  text = text.replace(/`([^`\n]+)`/g, (_m, code) => stash(`<code>${code}</code>`));

  // ৪) লিংক — শুধু http/https (নিরাপদ)
  text = text.replace(
    /\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g,
    (_m, label, url) => `<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>`,
  );

  // ৫) বোল্ড / ইটালিক / স্ট্রাইক
  text = text
    .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^_\n]+)__/g, "<strong>$1</strong>")
    .replace(/(^|[\s(])\*([^*\n]+)\*/g, "$1<em>$2</em>")
    .replace(/~~([^~\n]+)~~/g, "<del>$1</del>");

  // ৬) লাইন ধরে ধরে হেডিং / লিস্ট / কোট / প্যারা
  const html = [];
  let list = "";
  let quote = [];

  const closeList = () => {
    if (list) { html.push(`</${list}>`); list = ""; }
  };
  const closeQuote = () => {
    if (quote.length) { html.push(`<blockquote>${quote.join("<br>")}</blockquote>`); quote = []; }
  };
  const openList = (kind) => {
    closeQuote();
    if (list === kind) return;
    closeList();
    html.push(`<${kind}>`);
    list = kind;
  };

  for (const line of text.split("\n")) {
    const trimmed = line.trim();

    if (!trimmed) { closeList(); closeQuote(); continue; }

    if (/^\u0000\d+\u0000$/.test(trimmed)) { closeList(); closeQuote(); html.push(trimmed); continue; }

    const heading = /^(#{1,4})\s+(.*)$/.exec(trimmed);
    if (heading) {
      closeList(); closeQuote();
      const level = Math.min(6, heading[1].length + 1); // # → h2, ## → h3
      html.push(`<h${level}>${heading[2]}</h${level}>`);
      continue;
    }

    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) { closeList(); closeQuote(); html.push("<hr>"); continue; }

    const bullet = /^[-*•]\s+(.*)$/.exec(trimmed);
    if (bullet) { openList("ul"); html.push(`<li>${bullet[1]}</li>`); continue; }

    const numbered = /^\d{1,2}[.)]\s+(.*)$/.exec(trimmed);
    if (numbered) { openList("ol"); html.push(`<li>${numbered[1]}</li>`); continue; }

    // ">" আগেই &gt; হয়ে গেছে — তাই সেটাই দেখি
    const quoted = /^&gt;\s?(.*)$/.exec(trimmed);
    if (quoted) { closeList(); quote.push(quoted[1]); continue; }

    closeList(); closeQuote();
    html.push(`<p>${trimmed}</p>`);
  }
  closeList();
  closeQuote();

  // ৭) সরিয়ে রাখা কোড ব্লক/ইনলাইন কোড ফিরিয়ে আনি
  return html.join("").replace(/\u0000(\d+)\u0000/g, (_m, i) => vault[Number(i)] ?? "");
}

/** চ্যাটের শিরোনাম — প্রথম লাইনের প্রথম কয়েক শব্দ। */
export function titleFrom(text, limit = 34) {
  const clean = String(text ?? "").replace(/\s+/g, " ").trim();
  if (!clean) return "নতুন চ্যাট";
  return clean.length > limit ? `${clean.slice(0, limit)}…` : clean;
}
