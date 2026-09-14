# Testing Strategy — The Lenny Growth Assistant

## Testing pyramid for this system
```
        /  Manual UI walkthrough  \      ~15 scripted checks, run once before submission
       /   Integration (API+DB)    \     ~10-15 tests, real Postgres, mocked LLM
      /   Unit (logic, no I/O)      \    ~20-30 tests, fast, run on every change
```

## Strategy by component

| Component | Test type | What's covered |
|---|---|---|
| Chunking (`ingest.py`) | Unit | Chunk size/overlap correctness, paragraph-boundary respect, idempotent content-hash on re-run |
| Provider abstraction | Unit | Fallback triggers correctly on simulated timeout/auth error; no fallback when `LLM_FALLBACK_TO_LOCAL=false` |
| Retrieval service | Integration | Given a fixture transcript, expected chunk(s) retrieved above similarity threshold; **empty-result path returns "insufficient grounding," never a fabricated answer** |
| Agent routing | Unit | Sample messages route to the correct tool (QA vs. essay vs. artifact) based on intent phrasing |
| Session/message persistence | Integration | CRUD round-trip against a real (test) Postgres container; migrations apply cleanly from empty |
| Artifact sanitizer | Unit (security) | Table-driven tests with malicious payloads: `<script>`, `onerror=`, `javascript:` URLs — all confirmed stripped |
| API contracts | Integration | Request validation (422 on bad input), structured error shape, `/health` reflects real DB/provider/Ollama state |
| Frontend | Manual (v1) | Automated component tests are P1; v1 relies on the scripted manual pass below given the time budget — documented trade-off, not an oversight |

**Skipped deliberately:** trivial getters/setters, Pydantic model definitions themselves, framework boilerplate.

## Manual UI test plan (run before submission)
1. Start a new chat — empty state shows suggested prompts, not a blank box.
2. Ask a question answerable from the corpus — response includes at least one resolvable citation.
3. Ask a follow-up — context from the first turn is reflected in the answer.
4. Ask a question clearly outside the corpus — assistant explicitly declines rather than guessing.
5. Request a Ship 30/30 essay — verify ~1,250 words, hook, headings, bold emphasis, and a clear takeaway.
6. Request a Markdown artifact — renders in the viewer panel beside chat.
7. Request an HTML artifact — renders in the sandboxed viewer; confirm via devtools that no injected script executes.
8. Toggle `LLM_PROVIDER=ollama` and restart — UI badge reflects local model; a question is answered fully offline.
9. Remove the Anthropic API key with `LLM_FALLBACK_TO_LOCAL=true` — fallback banner appears, no crash.
10. Stop the Postgres container — app shows a clear error, not a hang or stack trace.
11. Stop Ollama while it's the active provider (no fallback configured) — clear structured error surfaced.
12. Resize to tablet width — artifact viewer becomes a toggle panel, not a broken layout.
13. Resize to mobile width — single-column, swipeable/tabbed views.
14. Keyboard-only pass — create a session, send a message, open an artifact, all without a mouse.
15. Fresh clone + `docker compose up` on a clean machine (or clean state) — full stack reachable with zero manual steps beyond documented `.env` setup.
