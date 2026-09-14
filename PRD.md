# PRD — The Lenny Growth Assistant

**Owner:** [Your name] · **Status:** Draft v1 · **Target ship date:** 15 Sep 2026 EOD

---

## 1. Forward Deployment Discovery Brief

### User and problem
**Primary user:** A product manager or growth practitioner (IC to Director level) on the client's internal team who already consumes Lenny's Podcast/Newsletter and wants to *operationalize* that knowledge instead of re-listening to episodes.

**Job to be done (JTBD framing):**
> "When I have a specific PM/growth question, or need to produce credible written content quickly, I want to query the collective knowledge inside Lenny's back-catalog so I get a grounded, cited answer or a publish-ready draft — without manually scrubbing transcripts or trusting an LLM's unverified memory."

**Pain removed:**
- Hours spent searching/skimming podcast transcripts or YouTube timestamps for "didn't someone talk about pricing experiments?"
- The blank-page problem when drafting thought-leadership content (LinkedIn posts, internal memos, Ship 30/30-style essays).
- The credibility risk of a generic LLM confidently inventing a quote or framework "from Lenny's podcast" that was never actually said.

**Who does NOT have this problem (scope guardrail):** external customers, non-PM/growth roles, anyone needing legal/financial advice. This is an internal knowledge tool, not a public product.

### Discovery methodology note (proxy research)
A real engagement would run 5–8 user interviews before writing a line of code (see `design:user-research` framework — interviews are the right method here: sample size 5–8, small enough to run in days). **A 48-hour take-home has no time budget for that**, so this PRD explicitly substitutes:
- Desk research on who follows Lenny's Newsletter/Podcast (PMs, growth leads, founders — publicly known audience).
- Structural inference from the brief itself (it says "product and growth team," "users want grounded answers, reusable written content, and rendered artifacts").
- A named **riskiest assumption** (below) and the cheapest way to test it, rather than pretending we validated something we didn't.

**Riskiest assumption:** Users trust and adopt a RAG assistant over just re-listening/searching *only if* citations are visibly verifiable and the "I don't know" case is honest. If grounding is weak or citations are fake, the tool is worse than useless — it's actively misleading. **Cheapest test:** in the demo, deliberately ask a question the corpus can't answer and show the assistant declining gracefully instead of hallucinating. This is now a P0 acceptance criterion (see §5), not a nice-to-have.

### Success metric
Two tiers, since there are no real users yet:

| Tier | Metric | Target | How measured |
|---|---|---|---|
| **Evaluation-phase (measurable now)** | % of test queries against the seeded transcript corpus that return either a valid, resolvable citation or an explicit "insufficient grounding" response — with **zero** fabricated citations | ≥ 90% grounded-or-honest, 0% fabricated | Automated retrieval/grounding test suite (see `TESTING_STRATEGY.md`) |
| **Hypothetical production north star** | % of chat sessions that end in a copied/downloaded artifact (proxy for "this saved me from writing from scratch") | 40% within first month of internal rollout | Product analytics event on artifact copy/download (P1 instrumentation, not built for v1) |

### Assumptions (explicit, because the brief is intentionally ambiguous)
1. No auth requirement stated → v1 is single-tenant, no login; a session is identified by a client-generated session token. Documented as a P1 gap, not silently ignored.
2. No specified transcript volume → ingest a **representative subset** (~20–40 episodes) for the demo rather than the full historical archive, to keep ingestion time and vector counts inside the time budget. Full-corpus ingestion is one documented command away.
3. "Users" are internal staff, not paying customers → no billing, quotas, or rate-limiting business logic.
4. Single demo user at a time — not built for concurrent load or multi-session race conditions beyond basic DB correctness.
5. Local model (Ollama) is "good enough to demonstrate the toggle works," not equivalent in quality to Claude — this gap is treated as an accepted, documented risk, not something to over-engineer around.
6. English-only content and UI.
7. No persisted feedback loop (thumbs up/down) in v1 — logged as a P1.
8. The "client engineer" doing handoff is technically competent (comfortable with Docker, `.env` files, shell) — README can use commands, not screenshots-for-non-technical-users.
9. Artifacts are viewed/copied/downloaded within-session only — no public share links (materially larger security surface, out of scope).

### Scope choices

**Included (v1 / P0):**
- FastAPI backend with sessions, persistence, health checks
- RAG grounded Q&A over ingested transcripts with visible citations
- Cloud (Anthropic Claude) + local (Ollama) model toggle with documented fallback
- Ship 30 for 30 essay skill, encoded as a structured skill (not an ad hoc prompt)
- Markdown + HTML/CSS artifact generation with a sandboxed in-app viewer
- Docker Compose one-command startup
- Structured logging, core resilience handling, automated + manual tests
- README, PRD, design.md, architecture.md, agent transcripts

**Intentionally excluded, with rationale:**

| Excluded | Why |
|---|---|
| User auth / multi-tenant orgs | Not requested; adds surface area disproportionate to 48-hr scope |
| Token-by-token streaming (SSE) | Nice UX, but complicates provider-fallback logic under time pressure. P1 if time allows |
| Full historical transcript ingestion | Demo subset only; documented follow-up command for full run |
| Fine-tuning, analytics dashboards, RLHF loops | Over-engineering for a take-home; no evidence of need yet |
| Public artifact sharing/export links | Materially larger security surface for unclear value in v1 |
| Full CI/CD pipeline | A basic lint/test GitHub Action is P1; not P0 |

---

## 2. Goals
1. Answer PM/growth questions **strictly and verifiably** from Lenny's transcripts, including follow-ups, within a single session.
2. Turn a grounded answer into a Ship 30/30-style essay via a **named, reusable skill**, not a one-off prompt.
3. Generate Markdown/HTML artifacts that render safely, natively, beside the chat.
4. Let an evaluator switch cloud ↔ local models via config, with visible state and graceful fallback.
5. Leave a system another engineer can run, test, and extend within an hour of cloning the repo.

## 3. Non-Goals
- Building a production-grade, multi-tenant SaaS product (this is a demo/evaluation deployment).
- Achieving local-model output quality parity with Claude (documented, accepted gap).
- Real-time collaborative editing of artifacts.
- Supporting non-English transcripts or queries.

## 4. User Stories

**Grounded Q&A**
- As a PM, I want to ask a product/growth question and get an answer with citations to specific episodes, so I can trust and verify the source.
- As a PM, I want to ask a follow-up question in the same session and have the assistant remember prior context, so I don't have to re-explain myself.
- As a PM, I want the assistant to tell me clearly when the transcripts don't support an answer, so I'm never misled by a confident guess.

**Content generation**
- As a growth lead, I want to turn a grounded discussion into a ~1,250-word Ship 30/30-style essay with a hook, headings, and a clear takeaway, so I can publish quickly without starting from a blank page.
- As a growth lead, I want the essay's claims grounded in the same transcript knowledge base, so what I publish is defensible.

**Artifacts**
- As a user, I want to request a Markdown or HTML artifact from the current conversation and see it rendered beside the chat, so I don't have to copy raw code into another tool.
- As a user, I want to trust that a generated HTML artifact can't run arbitrary scripts against my session, so I don't have to think about security myself.

**Model configuration**
- As an evaluator, I want to see which model (cloud or local) is currently answering, so I can verify the local-Ollama requirement is genuinely met.
- As an evaluator, I want the app to degrade gracefully (not crash) if my Anthropic API key is missing or Ollama isn't running, so I can still evaluate partial functionality.

**Handoff**
- As a client engineer, I want a single documented command to stand up the whole stack, so I can evaluate it without reverse-engineering the code.

## 5. Requirements (MoSCoW)

### Must-Have (P0)
| Requirement | Acceptance criteria |
|---|---|
| Session creation & persistence | Given a new chat request, when the user sends a first message, then a session row and message rows are created in Postgres with timestamps and a session ID returned to the client |
| Grounded Q&A with citations | Given a question answerable from the corpus, when the assistant responds, then the response includes at least one citation resolvable to a real ingested source |
| Honest "no answer" case | Given a question outside the corpus, when the assistant responds, then it explicitly states it cannot find supporting material — **no fabricated citation is produced** |
| Follow-up context | Given an existing session, when a follow-up message is sent, then prior turns are included in context and the answer reflects that continuity |
| Ship 30/30 skill | Given a request to turn an answer into an essay, when the skill runs, then the output is ~1,250 words, has a hook, headings/bullets/bold, a specific takeaway, and grounded claims |
| Artifact generation + viewer | Given a request for an artifact, when generated, then it renders in a dedicated panel beside the chat (not raw code, not a redirect) |
| Artifact sandboxing | Given a generated HTML artifact, when rendered, then it cannot execute arbitrary JavaScript against the parent app or access its cookies/storage |
| Model toggle visibility | Given the app is configured for provider X, when the UI loads, then the active provider/model is visibly displayed |
| Local Ollama demo path | Given `LLM_PROVIDER=ollama`, when a question is asked, then it is answered using the local model with no cloud call required |
| Graceful failure modes | Given a missing API key, unreachable Ollama, DB outage, or empty retrieval, when triggered, then the user sees a clear structured error, not a stack trace or hang |
| One-command startup | Given a fresh clone, when `docker compose up` (or documented equivalent) is run, then the full stack becomes reachable without manual DB setup |

### Should-Have (P1)
- Token-by-token streaming responses
- Full transcript corpus ingestion path (beyond the demo subset)
- Persisted user feedback (thumbs up/down) on messages
- Basic CI (lint + automated tests on push)
- Citation deep-linking to approximate transcript timestamp

### Won't-Have This Time (P2)
- Auth / multi-tenant orgs
- Public artifact sharing links
- Interactive (JS-executing) artifacts
- Analytics dashboards / fine-tuning

## 6. Open Questions
- **[Engineering]** Is GPU available on the evaluator's/your machine for a reasonably capable local model (7–8B), or should we plan around CPU-only inference speed? *(Non-blocking — default to a small quantized model and document the assumption.)*
- **[Product]** Should the essay skill's tone follow Lenny's own voice specifically, or a generic Ship 30/30 house style? *(Non-blocking — default to Ship 30/30 house style per the linked guide, since that's what's explicitly required.)*
- **[Legal/Data]** Any restriction on redistributing/quoting podcast transcript content in generated essays? *(Non-blocking for a demo; flag in README as a real-world consideration.)*

## 7. Timeline
- **Hard deadline:** 15 Sep 2026 EOD (submission form + demo video).
- No phased release — this ships as a single v1 given the take-home format. See `EXECUTION_PLAN.md` for the hour-by-hour build sequence and checkpoint discipline.
