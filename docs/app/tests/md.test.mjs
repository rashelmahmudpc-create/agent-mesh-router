/**
 * 🧪 মার্কডাউন রেন্ডারারের পরীক্ষা — `cd web && node --test tests/`
 * সবচেয়ে জরুরি: এজেন্টের লেখা কখনো HTML/স্ক্রিপ্ট হিসেবে চলবে না।
 */

import test from "node:test";
import assert from "node:assert/strict";

import { renderMarkdown, escapeHtml, titleFrom } from "../js/md.js";

test("html escape হয়", () => {
  assert.equal(escapeHtml('<img src=x onerror="alert(1)">'), "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;");
});

test("script ট্যাগ কখনো চলে না", () => {
  const html = renderMarkdown('<script>alert("hack")</script>');
  assert.ok(!html.includes("<script"));
  assert.ok(html.includes("&lt;script&gt;"));
});

test("বোল্ড আর ইটালিক", () => {
  assert.equal(renderMarkdown("**শক্ত** আর *হালকা*"), "<p><strong>শক্ত</strong> আর <em>হালকা</em></p>");
});

test("কোড ব্লক ভেতরের লেখা escape হয়, ফরম্যাট হয় না", () => {
  const html = renderMarkdown("```js\nconst a = '<b>';\n```");
  assert.ok(html.includes("<pre><code class=\"language-js\">"));
  assert.ok(html.includes("const a = &#39;&lt;b&gt;&#39;;"));
  assert.ok(!html.includes("<b>"));
});

test("ইনলাইন কোড", () => {
  assert.equal(renderMarkdown("চালান `npm test` এখন"), "<p>চালান <code>npm test</code> এখন</p>");
});

test("শুধু http/https লিংক হয়", () => {
  assert.ok(renderMarkdown("[জায়ান](https://example.com)").includes('href="https://example.com"'));
  assert.ok(!renderMarkdown("[খারাপ](javascript:alert(1))").includes("href="));
});

test("লিস্ট আর হেডিং", () => {
  const html = renderMarkdown("# শিরোনাম\n- এক\n- দুই\n1. প্রথম");
  assert.ok(html.includes("<h2>শিরোনাম</h2>"));
  assert.ok(html.includes("<ul><li>এক</li><li>দুই</li></ul>"));
  assert.ok(html.includes("<ol><li>প্রথম</li></ol>"));
});

test("কোট আর অনুভূমিক রেখা", () => {
  const html = renderMarkdown("> মনে রাখো\n\n---");
  assert.ok(html.includes("<blockquote>মনে রাখো</blockquote>"));
  assert.ok(html.includes("<hr>"));
});

test("খালি/অদ্ভুত ইনপুটেও ভাঙে না", () => {
  assert.equal(renderMarkdown(null), "");
  assert.equal(renderMarkdown(""), "");
  // ভেতরের গোপন প্লেসহোল্ডার-অক্ষরও নিরীহ থাকে
  assert.equal(renderMarkdown("a\u00000\u0000b"), "<p>a0b</p>");
});

test("শিরোনাম ছোট করা হয়", () => {
  assert.equal(titleFrom("  হাই   সবাই  "), "হাই সবাই");
  assert.equal(titleFrom(""), "নতুন চ্যাট");
  const long = titleFrom("ক".repeat(60));
  assert.ok(long.endsWith("…") && long.length <= 35);
});
