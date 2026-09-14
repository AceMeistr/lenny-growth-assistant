# Architecture — The Lenny Growth Assistant

## 1. Requirements recap (system-design framework)

**Functional:** chat sessions with persistence, RAG-grounded Q&A, essay-generation skill, artifact generation + rendering, cloud/local model toggle.
**Non-functional:** single-demo-user scale (not high concurrency), local-first resilience (must run with zero cloud dependency for the mandatory Ollama demo), evaluator can stand it up in minutes, secure-by-default artifact rendering.
**Constraints:** solo build, ~40 working hours, FastAPI + PostgreSQL mandated, must support Ollama.

## 2. High-level component diagram

```
                         ┌─────────────────────────┐
                         │        Frontend          │
                         │  React + Vite + Tailwind │
                         │  ┌───────┐  ┌───────────┐│
                         │  │ Chat  │  │ Artifact  ││
                         │  │ Pane  │  │ Viewer    ││
                         │  └───────┘  │ (sandboxed││
                         │             │  iframe)  ││
                         │             └───────────┘│
                         └───────────┬──────────────┘
                                     │ REST (JSON)
                                     ▼
                         ┌─────────────────────────┐
                         │       FastAPI backend    │
                         │  ┌─────────────────────┐ │
                         │  │ Session/Message API  │ │
                         │  ├─────────────────────┤ │
                         │  │ Agent Orchestrator   │ │◄── Claude Agent SDK
                         │  │ (tool/skill router)  │ │    (tool-use loop)
                         │  ├─────────────────────┤ │
                         │  │ LLMProvider (strategy)│──► Anthropic Claude (cloud)
                         │  ├─────────────────────┤ │──► Ollama (local, mandatory)
                         │  │ Retrieval Service     │ │
                         │  ├─────────────────────┤ │
                         │  │ Artifact Sanitizer    │ │
                         │  └─────────────────────┘ │
                         └───────────┬──────────────┘
                                     │
                                     ▼
                         ┌─────────────────────────┐
                         │  PostgreSQL + pgvector   │
                         │  sessions / messages /   │
                         │  transcript_chunks /     │
                         │  artifacts               │
                         └─────────────────────────┘

        (offline, CLI-only)
   scripts/ingest.py ──► clones lennys-podcast-transcripts ──► chunk ──► embed ──► upsert
```

## 3. Data flow

**Ingestion (offline, on-demand):**
`git pull transcripts repo → parse files → chunk (~800 tokens, 150 overlap, paragraph-aware) → content-hash for idempotency → embed (dual: cloud + local) → upsert into transcript_chunks with source metadata`

**Query (online):**
`user message → agent orchestrator → retrieval tool (vector search top-k) → if hits: grounded-answer prompt with citations; if no hits above threshold: "insufficient grounding" response → persist message + citations → return to client`

**Artifact generation:**
`user requests artifact → agent calls generate_artifact tool with conversation context → structured markdown/html returned → sanitized server-side → stored in artifacts table → frontend renders in sandboxed viewer`

## 4. Database schema (Postgres + pgvector)

```sql
create extension if not exists vector;

create table sessions (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  user_metadata jsonb not null default '{}',
  active_provider text not null default 'anthropic',
  active_model text
);

create table messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references sessions(id) on delete cascade,
  role text not null check (role in ('user','assistant','system')),
  content text not null,
  metadata jsonb not null default '{}',  -- citations, skill_used, latency_ms, provider, fallback_used
  created_at timestamptz not null default now()
);

create table transcript_sources (
  id uuid primary key default gen_random_uuid(),
  episode_title text not null,
  episode_url text,
  published_at date,
  raw_path text not null
);

create table transcript_chunks (
  id uuid primary key default gen_random_uuid(),
  source_id uuid not null references transcript_sources(id) on delete cascade,
  chunk_index int not null,
  content text not null,
  content_hash text not null unique,
  embedding_cloud vector(1024),
  embedding_local vector(768),
  token_count int not null
);
create index on transcript_chunks using ivfflat (embedding_cloud vector_cosine_ops);
create index on transcript_chunks using ivfflat (embedding_local vector_cosine_ops);

create table artifacts (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references sessions(id) on delete cascade,
  message_id uuid references messages(id),
  type text not null check (type in ('markdown','html')),
  title text,
  content text not null,
  created_at timestamptz not null default now()
);
```

## 5. API contracts

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness + readiness: checks DB connection, configured LLM provider reachability, Ollama reachability |
| `GET` | `/config` | Returns active provider/model (no secrets) for the UI badge |
| `POST` | `/sessions` | Create a new session |
| `GET` | `/sessions/{id}` | Fetch session + message history |
| `POST` | `/sessions/{id}/messages` | Send a user message; returns assistant response (+ citations, skill used, provider) |
| `GET` | `/sessions/{id}/artifacts` | List artifacts for a session |
| `GET` | `/artifacts/{id}` | Fetch a single artifact's content |

All endpoints return structured errors: `{"error": {"code": "...", "message": "...", "detail": "..."}}` with appropriate HTTP status — never a bare 500 with a traceback. Request bodies validated via Pydantic models; validation failures return 422 with field-level detail.

**Deliberately not an API endpoint:** ingestion. It's CLI-only (`python scripts/ingest.py`) to avoid exposing a data-mutation surface over HTTP with no auth in front of it.

## 6. Agent routing design

The agent orchestrator (Claude Agent SDK, tool-use loop) has three tools:

1. `search_transcripts(query, k=6)` — vector search against `transcript_chunks`, returns chunks + source metadata. Always called first for any substantive question — retrieval-before-answer is enforced by the system prompt and tool-choice policy, not left to model discretion, to reduce hallucination risk.
2. `write_ship30_essay(topic, grounding_chunks)` — the essay skill (see §8).
3. `generate_artifact(format, content_spec)` — produces markdown or html output.

Routing signal: explicit intent phrases ("turn this into an essay," "make this a doc/artifact") route to tools 2/3; everything else defaults to grounded Q&A via tool 1. This is intent-based routing, not a separate ML classifier — appropriate given the time budget and the clear phrasing patterns in the brief's own examples.

## 7. Model provider abstraction & fallback (ADR-1)

```
Status: Accepted
Context: Must support both a cloud provider and Ollama, switchable via config, without
  application-code changes, with graceful fallback.
Decision: An LLMProvider interface (AnthropicProvider, OllamaProvider, optional
  OpenAIProvider) selected via LLM_PROVIDER / LLM_MODEL env vars. Active provider/model
  surfaced via GET /config and shown in the UI header.
Fallback policy: if the configured cloud call fails (auth, rate-limit, timeout) and
  LLM_FALLBACK_TO_LOCAL=true, retry against the configured Ollama model and tag the
  response metadata with fallback_used=true so the UI can show a banner. If Ollama is
  also unreachable, return a structured 503, not a crash.
Consequences: (+) evaluator can flip one env var to fully demo local-only operation.
  (+) one failure mode away from total outage. (-) dual-path testing burden — mitigated
  by mocking providers in integration tests rather than hitting real models in CI.
```

## 8. Ship 30/30 skill design

Encoded as a structured skill (not an ad hoc prompt) with an explicit checklist derived from the linked guide:
- Target length ~1,250 words (soft-validated post-generation; regenerate once if >20% off target)
- Required structure: hook (first 1–2 sentences), skimmable headings/bullets, selective bold emphasis, one specific and useful takeaway at the end
- Claims must trace back to `search_transcripts` results passed in as grounding — the skill receives grounding chunks as input, it does not re-query freely, keeping the essay's claims auditable against the same citations used elsewhere.

## 9. Security: artifact rendering (ADR-2)

```
Status: Accepted
Context: Generated HTML is untrusted by definition — it's LLM output rendered inside
  the same browser tab as the user's session.
Decision: All HTML/CSS artifacts render inside a sandboxed <iframe sandbox="allow-same-origin">
  — deliberately WITHOUT allow-scripts. No JavaScript execution is permitted in v1;
  there is no legitimate use case in this assignment's examples (essays, formatted docs,
  landing-page snippets) that requires it. Server-side, content also passes through a
  sanitizer that strips <script> tags, inline event handlers (onclick, etc.), and
  javascript: URLs before storage — defense in depth even though the sandbox should
  already block execution. Markdown artifacts render via react-markdown + rehype-sanitize,
  never dangerouslySetInnerHTML on raw model output.
What the viewer permits: static HTML structure, CSS styling, images via https URLs.
What it blocks, and why: <script> execution (no legitimate need, largest exploit class),
  form submission to arbitrary origins, access to parent-page cookies/localStorage
  (iframe isolation), inline event handlers.
Consequences: (+) removes an entire exploit class by construction. (-) artifacts can't
  be interactive (e.g. a mini calculator) — documented P2: "interactive JS artifacts"
  behind an explicit opt-in and much stricter CSP, not attempted in v1.
```

## 10. Key decisions considered and rejected (brainstorm digest)

| Decision | Options considered | Chosen | Why |
|---|---|---|---|
| Vector store | pgvector vs. Chroma/Qdrant/Pinecone | **pgvector** | Already running Postgres for sessions; one DB, one backup story, one thing to containerize. Corpus size (~tens of thousands of chunks) is well within pgvector's comfortable range — revisit only if corpus grows ~100x |
| Embeddings | Single cloud model vs. dual cloud+local | **Dual, precomputed at ingestion** | Local Ollama demo path is mandatory; precomputing both avoids re-embedding on every provider toggle and avoids ever mixing incompatible vector spaces at query time |
| Frontend | Next.js vs. React+Vite | **React + Vite + TS + Tailwind** | No SSR/routing complexity needed for a single-page chat app; faster iteration under a 40-hour budget |
| Agent framework | Claude Agent SDK vs. Pi Coding Agent | **Claude Agent SDK** | First-party Python SDK, native tool/skill abstraction matches the assignment's explicit "encode it as a skill" requirement; Pi is oriented at coding-agent workflows, a mismatch for conversational RAG |
| Streaming | SSE token streaming vs. full-response | **Full-response for v1, SSE as P1** | Streaming complicates the fallback-retry path (can't silently retry a half-streamed response); ship correctness first |

## 11. Deployment topology

Docker Compose services: `backend` (FastAPI), `frontend` (React, served via Vite preview or nginx), `postgres` (with pgvector extension baked into the image). **Ollama runs on the host**, not inside Compose — GPU passthrough into containers is unreliable across evaluator machines, so the backend reaches it via `host.docker.internal:11434` (documented explicitly in README, with a pre-flight check surfaced through `/health`).

## 12. Observability & resilience

- Structured JSON logs (request ID, session ID, provider, latency_ms, retrieval hit count) for every message turn — enough to diagnose "was this a model problem, a retrieval problem, or a DB problem" without re-running the request.
- `/health` checks DB, active provider, and Ollama reachability independently so a partial outage is diagnosable at a glance.
- Every external call (LLM, embeddings, DB) wrapped with timeouts and typed exceptions mapped to structured error responses — no bare tracebacks reach the client.
