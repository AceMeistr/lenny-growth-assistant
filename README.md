# The Lenny Growth Assistant

A full-stack, conversational knowledge co-pilot grounded strictly in **Lenny’s Podcast** transcripts. Built for internal product and growth teams to query verified growth knowledge, transform discussions into structured **Ship 30 for 30** essays, and render live sandboxed HTML/CSS and Markdown artifacts beside the chat.

Designed with a **Human-Centric Native & AI-Negative aesthetic** (no neon purple gradients, no floating particle grids, no robot emojis) focusing on high-craft editorial publishing, clear typography, and scholarly citation transparency.

---

## Key Features

1. **Strictly Grounded Q&A**: Answers product management and growth questions with explicit bibliographic citation chips (episode, URL, timestamp snippet, similarity score).
2. **Honest "No Answer" Refusal (P0)**: If the ingested corpus lacks supporting evidence, the assistant explicitly states it cannot answer rather than hallucinating facts or citations.
3. **Ship 30 for 30 Content Skill**: Dedicated skill encoding atomic essay principles (~1,250 words, strong contrast hook, skimmable headings, bulleted anchors, single actionable takeaway).
4. **Sandboxed Artifact Studio (ADR-2)**: Side-by-side Claude-style split viewer. Static HTML and Markdown artifacts render securely in an isolated `<iframe sandbox="allow-same-origin">` (scripts stripped server-side and execution blocked).
5. **Flexible Multi-Model Architecture (ADR-1)**: Toggle between **Anthropic Claude** and local **Ollama** models via configuration or live UI badge, with automatic graceful fallback.
6. **System-Independent Execution ("Run Anywhere")**: Standardized Docker Compose containerization and bare-metal Python support (Postgres + pgvector with automatic SQLite fallback).

---

## Architecture Overview

```
                          +------------------------------------------+
                          |        Human-Centric Native UI           |
                          |  +------------+  +--------------------+  |
                          |  | Chat Pane  |  |  Artifact Studio   |  |
                          |  |  (Citations|  | (Sandboxed Iframe) |  |
                          |  +------------+  +--------------------+  |
                          +---------------------+--------------------+
                                                | REST (JSON)
                                                v
                          +------------------------------------------+
                          |             FastAPI Backend              |
                          |  +------------------------------------+  |
                          |  | Health (/health) & Config (/config)|  |
                          |  +------------------------------------+  |
                          |  | Session & Message Persistence      |  |
                          |  +------------------------------------+  |
                          |  | Agent Orchestrator & Skill Router  |  |
                          |  +------------------------------------+  |
                          |  | LLMProvider: Anthropic + Ollama    |  |
                          |  +------------------------------------+  |
                          |  | Vector Retrieval & HTML Sanitizer  |  |
                          |  +------------------------------------+  |
                          +---------------------+--------------------+
                                                |
                                                v
                          +------------------------------------------+
                          |          PostgreSQL + pgvector           |
                          |      (or SQLite zero-dep fallback)       |
                          +------------------------------------------+
```

---

## Quickstart & Deployment

### Option A: One-Command Docker Setup (Recommended)

Ensure Docker Desktop is running, then execute:

```bash
docker compose up --build
```

The application will be accessible at:
- **Web UI & Chat**: [http://localhost:8000](http://localhost:8000)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

### Option B: Local Bare-Metal (Python 3.11+)

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

3. **Ingest Seed Transcripts**:
   ```bash
   python -m scripts.ingest
   ```

4. **Verify Environment Setup**:
   ```bash
   python -m scripts.test_setup
   ```

5. **Start the Application**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

---

## Model Provider Configuration

The active model provider can be toggled without changing application code by editing `.env`:

### 1. Local Model (Ollama) — Mandatory Demo Path
Ensure Ollama is running on your machine with `phi3`:
```bash
ollama run phi3
```
In `.env`:
```ini
LLM_PROVIDER=ollama
LLM_MODEL=phi3
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=phi3
OLLAMA_EMBED_MODEL=phi3
```

### 2. Cloud Model (Anthropic Claude)
In `.env`:
```ini
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_API_KEY=your_actual_api_key_here
LLM_FALLBACK_TO_LOCAL=true
```

If `LLM_FALLBACK_TO_LOCAL=true` and your Anthropic API key is invalid or rate-limited, the application automatically catches the exception, routes the prompt to your local Ollama instance, and flags the response with a notice banner.

---

## Running the Automated Test Suite

Run the full pytest suite covering chunking, API contracts, retrieval refusal thresholds, and XSS sanitizer security:

```bash
python -m pytest tests/ -v
```

All 11 critical test scenarios pass:
- `test_health_endpoint`: Verifies DB and provider connectivity.
- `test_session_lifecycle`: Verifies session creation, message persistence, and retrieval.
- `test_compute_content_hash_deterministic`: Verifies SHA-256 chunk deduplication.
- `test_chunk_text_preserves_content_and_overlap`: Validates paragraph-aware chunk boundaries.
- `test_cosine_similarity_identical_and_orthogonal`: Tests vector math.
- `test_retrieval_threshold_refusal`: Enforces zero hallucinated citations on low similarity.
- `test_sanitize_html_removes_script_tags`: Proves XSS `<script>` neutralization.
- `test_sanitize_html_removes_inline_event_handlers`: Proves removal of `onclick`/`onerror`.
- `test_sanitize_html_removes_javascript_urls`: Proves blocking of `javascript:` links.

---

## Security Architecture (ADR-2)

All generated artifacts are treated as untrusted input. The viewer employs defense-in-depth:
1. **Server-Side Sanitization**: `ArtifactSanitizer` cleans input with BeautifulSoup before database storage, stripping forbidden tags (`<script>`, `<object>`, `<embed>`, `<form>`) and inline event handlers (`onload`, `onerror`).
2. **Client-Side Iframe Isolation**: HTML artifacts render inside an `<iframe sandbox="allow-same-origin">`. The `allow-scripts` token is deliberately omitted to prevent JavaScript execution.

---

## Project Structure

```
OOGWAY/
├── app/
│   ├── config.py              # Pydantic v2 environment settings
│   ├── db.py                  # Database connection, pooling, and fallback
│   ├── main.py                # FastAPI endpoints and static file mounts
│   ├── models/                # SQLAlchemy models and Pydantic validation schemas
│   ├── providers/             # Anthropic & Ollama strategy abstraction with fallback
│   ├── services/              # Retrieval, Agent orchestrator, Ship 30/30 skill, Sanitizer
│   └── static/                # Human-centric native UI (HTML, CSS tokens, ES modules)
├── data/
│   └── seed_transcripts.json  # Seed corpus from Lenny's podcast episodes
├── scripts/
│   ├── ingest.py              # CLI ingestion, chunking, and dual-embedder
│   └── test_setup.py          # Pre-flight environment diagnostics
├── tests/                     # Unit, integration, and security test suites
├── Dockerfile                 # Multi-stage production container
├── docker-compose.yml         # Compose stack (PostgreSQL + pgvector + FastAPI)
├── requirements.txt           # Pinned standard dependencies
└── README.md                  # Comprehensive operational documentation
```
