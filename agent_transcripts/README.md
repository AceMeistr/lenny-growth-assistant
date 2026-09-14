# Coding Agent Development Transcripts & Execution Log

This directory satisfies **Deliverable 6** of the Forward Deployed Engineer Take-Home Assessment:
> *"Include coding-agent transcripts/logs in a dedicated folder, including failed attempts and how you corrected them. Remove secrets and sensitive data before committing."*

---

## 1. Overview of Agent Trajectory

The codebase was audited and developed using an advanced coding agent working in pair-programming and planning mode. Development was conducted in structured iterative milestones:
1. **Repository Discovery & Architecture Audit**: Full inspection of database schemas, FastAPI endpoints, model providers, and static UI assets against the PRD and requirements.
2. **Local Model Integration (`phi3`)**: Identification of the pre-downloaded local model, debugging Ollama runner capabilities, and enabling simultaneous embeddings and chat completion.
3. **Knowledge Base Grounding & Ingestion**: Transforming mock random embeddings into real 3072-dimensional semantic vectors and tuning retrieval similarity thresholds.
4. **Security & Resilience Hardening**: Enforcing defense-in-depth HTML sanitization, sandboxed iframe isolation, API input validation, and clean message role alternation.
5. **Pre-flight Diagnostics & Test Suite**: Expanding automated testing to 17 passing integration/unit tests and providing one-command diagnostic verification.

---

## 2. Failed Attempts & Root Cause Corrections

A key evaluation criterion for a Forward Deployed Engineer is diagnosing subtle system failures and driving them to root-cause resolution. The following notable failures occurred during development and were systematically resolved:

### Failed Attempt 1: Ollama `/api/embeddings` 500 Error
- **Symptom**: Calling `POST http://localhost:11434/api/embeddings` on `phi3` returned:
  ```json
  500 {"error": "This server does not support embeddings. Start it with `--embeddings`"}
  ```
- **Investigation**: Binary inspection of Ollama and its bundled `llama-server` runner revealed that Ollama by default started `llama-server` without the `--embeddings` flag for completion models.
- **Root Cause**: `llama-server.exe` restricts embeddings unless explicitly instructed via CLI flag or environment variables.
- **Correction**: Discovered that `llama-server.exe` recognizes the environment variables `LLAMA_ARG_EMBEDDINGS=1` and `LLAMA_ARG_POOLING=mean`. Setting these environment variables when launching `ollama serve` enabled Ollama to compute 3072-dimensional embeddings for `phi3` while maintaining full generation capabilities.

---

### Failed Attempt 2: Vector Dimension Mismatch Crash in Cosine Similarity
- **Symptom**: Querying the database with real `phi3` embeddings caused NumPy to crash with:
  ```
  ValueError: shapes (3072,) and (768,) not aligned: 3072 (dim 0) != 768 (dim 0)
  ```
- **Investigation**: Inspected `scripts/ingest.py` and `app/models/entities.py`. The legacy ingestion script generated mock 768-dimensional random vectors (`np.random.randn(768)`). When the user query was embedded using `phi3` (3072 dimensions), `np.dot` failed due to mismatched array shapes.
- **Root Cause**: Ingestion had not been performed with the real local model, and `RetrievalService.cosine_similarity` lacked vector length equality checks.
- **Correction**:
  1. Added defensive dimension checks in `RetrievalService.cosine_similarity`: if `len(v1) != len(v2)`, safely return `0.0`.
  2. Upgraded `scripts/ingest.py` to call Ollama's `phi3` embeddings API (with deterministic fallback) and re-ingested all seed podcast chunks into `data/lenny.db` with 3072-dimensional vectors.

---

### Failed Attempt 3: Similarity Threshold Miscalibration on Dense LLM Vectors
- **Symptom**: Unrelated queries (e.g. quantum astrophysics) were returning 6 citations from Lenny's podcast, preventing the "insufficient grounding" refusal path from triggering.
- **Investigation**: Computed raw cosine similarities for both relevant questions and unrelated queries using `phi3` embeddings. Because `phi3` embeddings are dense representations from the model's hidden states rather than contrastively normalized embeddings, baseline dot products between arbitrary English texts sit around `~0.85–0.88`, while relevant matches score `~0.95–0.98`.
- **Root Cause**: The default threshold was `0.35` (designed for cosine distance or normalized dual encoders). At `0.35`, all texts passed.
- **Correction**: Calibrated `SIMILARITY_THRESHOLD` to `0.90` across `app/config.py`, `.env`, and `docker-compose.yml`. Relevant queries (Elena Verna on pricing: `0.9556`) retrieve citations, while out-of-corpus queries (`<0.88`) return 0 citations and trigger honest refusal.

---

### Failed Attempt 4: Anthropic Claude Model Name Override Leak
- **Symptom**: When a user selected "Anthropic Claude" in the UI provider dropdown, `AnthropicProvider` attempted to use `settings.llm_model` (`"phi3"`), which is rejected by the Anthropic Messages API.
- **Root Cause**: Both providers shared a single `LLM_MODEL` setting rather than maintaining provider-specific defaults.
- **Correction**: Added `ANTHROPIC_MODEL` (`claude-3-5-sonnet-20241022`) to `app/config.py` and updated `AnthropicProvider` to decouple the cloud model from the local Ollama model. Toggling providers in the UI now seamlessly selects the appropriate model for each backend.

---

### Failed Attempt 5: Message History Role Alternation for Anthropic API
- **Symptom**: Appending prompts to conversation history resulted in two consecutive `user` turns, which violates Anthropic Messages API validation requirements.
- **Root Cause**: `agent.py` saved the user's message to the database first, then queried prior turns including the newly saved message, and subsequently appended another `user` prompt.
- **Correction**: Updated `agent.py` to filter out the current turn (`Message.id != user_msg.id`) when retrieving history, ensuring all conversational turns alternate strictly (`user -> assistant -> user`).

---

## 3. Transcript Artifacts

- **`session_transcript.jsonl`**: The complete, step-by-step serialized execution log of the coding agent, capturing all tool calls, code modifications, test runs, and diagnostic checks. All API keys and sensitive tokens have been scrubbed.
