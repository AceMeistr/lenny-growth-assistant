# Execution Plan — The Lenny Growth Assistant

**Now:** Sun 13 Sep 2026 · **Due:** Tue 15 Sep 2026 EOD · **Budget:** ~60 raw hours / ~35–40 working hours after sleep.

This is the connective tissue across `PRD.md`, `architecture.md`, `design.md`, and `TESTING_STRATEGY.md` — the sequencing, the risk register, and the pre-committed cut list so decisions under pressure are fast, not agonized.

---

## 1. The one assumption this whole plan bets on

Per the brainstorming framework's "assumption testing" mode: **the riskiest assumption isn't a product assumption — it's a feasibility one.** *"A solo builder can get retrieval + agent + artifact + resilience + docs demo-ready in ~35 working hours."*

**Cheapest test:** build the walking skeleton (ingest → retrieve → grounded answer, end-to-end, ugly UI) *first*, inside the first ~10 hours. If that alone blows the budget, the cut list below activates immediately — no re-litigating scope while the clock is running.

**Pre-committed cut list (in order, if behind schedule):**
1. Drop HTML artifacts → Markdown only (cut ADR-2's sandboxing work in half)
2. Drop the local+cloud dual embedding path → local Ollama only, skip the cloud model entirely for embeddings (cloud LLM chat can still work, cite it as a documented gap)
3. Shrink transcript subset from ~30 episodes to ~10
4. Drop automated frontend polish (responsive/a11y) → document as known P1, keep functional
5. Never cut: grounded citations, the "insufficient grounding" honesty path, or the demo video — these are the eval criteria most likely to sink the submission if missing

## 2. Build sequence

| Block | When | Focus | Exit criteria |
|---|---|---|---|
| **0** | Sun 13, remaining hours (~5h) | Repo scaffold, Docker Compose skeleton, `.env.example`, DB schema/migrations, FastAPI `/health` skeleton, clone+inspect transcripts repo, lock ADRs from `architecture.md` | `docker compose up` boots empty stack; schema applied |
| **1** | Mon 14 AM (~4h) | Ingestion pipeline end-to-end for the subset; session/message CRUD + persistence; request/response validation | Can run `ingest.py` and query chunks back from Postgres |
| **2** | Mon 14 PM (~5h) | Agent orchestrator (Claude Agent SDK) + `search_transcripts` tool wired to cloud provider; provider abstraction + Ollama path + fallback | A question gets a grounded, cited answer via cloud Claude |
| **3** | Mon 14 evening (~3.5h) | Ship 30/30 skill; artifact generation tool (markdown first, html second); artifact endpoints | Essay skill produces a checklist-passing draft from a real answer |
| **4** | Tue 15 AM (~4h) | Frontend: chat UI, session list, sandboxed artifact viewer, provider badge, core states from `design.md` | Full loop works in the browser, not just via curl |
| **5** | Tue 15 midday (~3h) | Resilience pass (all 5 failure modes), structured logging, automated tests per `TESTING_STRATEGY.md` | All P0 tests green; manual test plan run once |
| **6** | Tue 15 early PM (~2.5h) | README finalize, docs reconciled with what was actually built, agent transcripts folder scrubbed of secrets, clean-clone smoke test | A fresh clone works from README alone |
| **7** | Tue 15 late PM (~1.5h) | Record 2–3 min demo video (camera on), upload to YouTube, submit form | Submitted with buffer before EOD |

## 3. Status checkpoints (stakeholder-update discipline, applied to yourself)

Run this exact exercise at the end of Blocks 0, 3, and 5. Being honest here is the entire point — a Yellow caught Monday morning is a scope cut; a Yellow discovered Tuesday night is a missed deadline.

**Day-0 kickoff status (pre-filled — start here):**
```
Status: Yellow
TL;DR: Scope is tight but deliberately cut to fit; walking skeleton is the Block-0/1 bet.
Progress: PRD, architecture, design, and testing strategy drafted and decision-locked.
Risks (ROAM):
- Owned: 35-hour budget vs. full feature list → mitigated via pre-committed cut list above.
- Accepted: local-model output quality will lag Claude noticeably → documented in PRD, not hidden.
- Owned: Claude Agent SDK is a new dependency under time pressure → if it costs >3h beyond
  plan in Block 2, fall back to a hand-rolled tool-call loop (same interface, less framework).
Decisions needed: none blocking — architecture is locked, build now.
Next milestone: Block 0 exit criteria (stack boots, schema applied) by end of today.
```

**Template to fill in at end of Block 3 (Monday EOD) and Block 5 (Tuesday midday):**
```
Status: [Green/Yellow/Red — be honest, not optimistic]
TL;DR:
Progress since last checkpoint:
Risks (ROAM):
Decisions needed:
Next milestone:
```

## 4. Mapping this plan to the evaluation criteria
- **Customer & product judgment** → PRD §1 discovery brief, named riskiest assumption, explicit non-goals
- **Technical execution** → Blocks 1–5, `architecture.md` §§4–8
- **Agentic architecture & grounding** → §6 routing design, the "insufficient grounding" P0 requirement (never cut, per §1 above)
- **Deployment & operability** → Block 0 Docker Compose, `architecture.md` §11–12, README (Block 6)
- **Code quality** → enforced by keeping Blocks scoped and tested rather than sprawling
- **UI/UX quality** → `design.md`, Block 4
- **Communication** → this document + PRD + architecture + design + the demo video script below

## 5. Demo video script skeleton (2–3 min, camera on)
1. **(20s)** The problem: PMs want grounded answers + reusable content from Lenny's back-catalog without re-listening to hours of podcast.
2. **(60s)** Live demo: ask a grounded question (show citation), ask a follow-up, trigger the Ship 30/30 skill, generate and view an artifact.
3. **(30s)** Switch to local Ollama live, ask the same question, point out the UI badge change.
4. **(30s)** One real trade-off, stated plainly: e.g., "I chose pgvector over a dedicated vector DB to avoid a second piece of infrastructure — here's what I'd revisit if the corpus grew 100x."

## 6. Immediately actionable next step
This plan is the design phase. The build phase is exactly the kind of work Claude Code is suited for — and the assignment already requires you to submit agent-transcripts as a deliverable, so working in Claude Code from here gets you that artifact for free while you build Block 0.
