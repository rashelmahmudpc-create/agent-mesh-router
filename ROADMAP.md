# Roadmap

## Phase 1: Foundation
- Define repository purpose and scope
- Establish architecture and agent boundaries
- Create minimum orchestration loop
- Define session and task models

## Phase 2: Core Routing
- Build router logic
- Add task classification
- Add route selection
- Implement basic agent registry

## Phase 3: Tool Integration
- Add GitHub integration
- Add external API adapter layer
- Add Cloudflare and infrastructure hooks
- Add environment-based secret handling

## Phase 4: Multi-Agent Workflows
- Add planner, coder, reviewer, and tool agents
- Add event-driven communication
- Add validation checkpoints
- Add human approval gates for high-risk actions

## Phase 5: Scaling and Observability
- Add logs, traces, and session monitoring
- Add memory persistence
- Add queue or worker infrastructure
- Add dashboard for runs and statuses

## Phase 6: Production Hardening
- Security controls
- Permission boundaries
- Agent policy enforcement
- Deployment automation
- Real-world integration testing

## Long-Term Vision
- Multi-tenant agent infrastructure
- Shared orchestration network
- Dynamic tool discovery
- Cross-agent memory propagation
- Enterprise workflow automation

---

## অগ্রগতি (2026-10-25)

| ফেজ | অবস্থা | প্রমাণ |
|---|---|---|
| ১. Foundation | ✅ হয়েছে | `config/agents.json`, সেশন/কাজের মডেল (`Reply`, `Store`) |
| ২. Core Routing | ✅ হয়েছে | `mesh/router.py` — mention/keyword রাউটিং, direct + group |
| ৩. Tool Integration | 🟡 আংশিক | `gh` দিয়ে Issue/comment (হলঘর), key rotation; Cloudflare বাকি |
| ৪. Multi-Agent | 🟡 আংশিক | গ্রুপ চ্যাট + এজেন্ট↔এজেন্ট mention; human approval gate বাকি |
| ৫. Observability | 🟡 আংশিক | `.mesh/transcript.jsonl`, ডক্টর, CI; dashboard বাকি |
| ৬. Hardening | 🟡 আংশিক | `redact()`, approve-gate নিয়ম ব্রেইনে; ডিপ্লয়মেন্ট বাকি |
