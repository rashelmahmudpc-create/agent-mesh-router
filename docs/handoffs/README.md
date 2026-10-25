# Handoffs

প্রতিটা কাজের শেষে একটা হ্যান্ডঅফ ফাইল এখানে রাখুন — পরের এজেন্ট যাতে জিজ্ঞেস না করেই কাজ ধরতে পারে।

**নামের নিয়ম:** `YYYY-MM-DD-<topic>.md` → যেমন `2026-10-25-mesh-bootstrap.md`

---

## Template (কপি করে নতুন ফাইল বানান)

```markdown
# Handoff — <topic> (<date>)

**Asked:** এক-দুই লাইনে মূল অনুরোধ
**Priority:** 1–5 (AGENTS.md §4 দেখুন)
**Role:** planner / worker / reviewer

**Done:**
- কোন ফাইল বদলেছে
- কোন কমান্ড চালানো হয়েছে

**Verified:**
$ <command>
<আসল আউটপুট>

**Still open:**
- পরের নির্দিষ্ট ধাপ

**Do not touch:**
- ফাঁদ, অর্ধেক-কাজ, জড়িত গোপন তথ্য
```

> ⚠️ হ্যান্ডঅফে কখনো key, token, ছাত্রের ডেটা লিখবেন না।
