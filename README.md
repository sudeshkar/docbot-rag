# DocBot: multi-tenant RAG support bots

Upload your docs or crawl your site, and get an embeddable AI support widget that answers with **citations**. DocBot also tracks the questions your docs **couldn't answer**.

**Stack:** Next.js · FastAPI · PostgreSQL (app data + full-text search) · **Chroma** (vectors) · Redis + arq (background jobs) · Claude or Groq (answers) · Voyage (embeddings)

## Features

- **Multi-tenant SaaS.** Accounts, multiple bots per user, and per-bot isolation: one Chroma collection per bot, and every SQL query is scoped by `bot_id`.
- **Ingestion.** PDF (with page numbers), Markdown and text uploads, a single URL, or a full-site BFS crawl. All of it runs in a background worker.
- **Four chunking strategies, chosen per bot:**
  - **fixed:** a token window with overlap.
  - **recursive:** paragraph → line → sentence → word.
  - **markdown:** heading-aware (the default).
  - **semantic:** splits where meaning shifts, using embeddings.

  Every strategy also gets contextual chunk headers and deduplication.
- **Hybrid retrieval.** Chroma vector search plus Postgres full-text search, fused with Reciprocal Rank Fusion.
- **Grounded, streaming answers.** Claude streams the answer over SSE, with inline `[n]` citations and hover cards showing the source snippet.
- **Embeddable widget.** One `<script>` tag, with an origin allowlist, per-IP rate limits, a monthly quota and key rotation.
- **Analytics.** Daily volume, answer rate, latency, tokens, the most-cited documents, and **unanswered questions** (what to write docs for next).
- **Evaluation harness.** Compares every chunking strategy against vector, keyword and hybrid retrieval on a golden set, reporting recall@k and MRR.
- **Security hardening.** SSRF-safe crawler, upload validation, prompt-injection escaping, IDOR protection, login throttling and security headers. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#security-model).

Architecture, low-level design (class diagram and patterns), complexity notes and the threat model are in **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

## Quick start

Prerequisites: Docker, Python 3.12+, Node 20+.

```bash
# 1. Infrastructure: Postgres :5433, Chroma :8001, Redis :6380
docker compose up -d

# 2. API
cd api
python -m venv .venv && .venv/Scripts/activate   # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add ANTHROPIC_API_KEY and VOYAGE_API_KEY, and set a long random JWT_SECRET
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 3. Worker (second terminal, in api/)
arq app.worker.WorkerSettings

# 4. Web (third terminal)
cd web
cp .env.example .env.local
npm install
npm run dev                 # http://localhost:3000
```

No API keys yet? Set `EMBEDDING_PROVIDER=hash` to ingest and search offline. For chat, use either `ANTHROPIC_API_KEY`, or `LLM_PROVIDER=groq` with a `GROQ_API_KEY` (default model `openai/gpt-oss-120b`, override with `GROQ_MODEL`).

Try it with `sample_docs/acme-help-center.md`. Embed the widget on any page with:

```html
<script src="http://localhost:3000/widget.js" data-key="pk_..." async></script>
```

## Tests

The backend was built test-first.

```bash
cd api
pytest                    # all tests (integration tests need docker compose up)
pytest -m "not integration"
cd ../web && npm test     # frontend unit tests (Vitest)
```

## Retrieval evaluation

```bash
cd api
python -m evals.run_eval                    # offline hash embeddings
python -m evals.run_eval --embedder voyage  # real embeddings
```

Results on the bundled 16-question golden set, with offline hash embeddings and k = 5:

| Chunking | Chunks | Hybrid R@1 | Hybrid MRR | Keyword R@1 | Vector R@1 |
|---|---|---|---|---|---|
| fixed | 3 | 0.69 | 0.83 | 0.81 | 0.69 |
| recursive | 3 | 0.62 | 0.81 | 0.69 | 0.56 |
| **markdown** | 12 | **0.81** | **0.91** | 0.88 | 0.69 |
| semantic | 15 | 0.81 | 0.90 | 0.88 | 0.69 |

Structure-aware chunking wins at rank 1. The corpus is small, so R@5 saturates; add your own docs and golden questions in `api/evals/` for a meaningful comparison. Hash embeddings are a weak offline stand-in, so expect vector and hybrid scores to rise with Voyage.

## Project layout

```
api/app/
  core/           config, auth (bcrypt + JWT)
  db/             SQLAlchemy models, session
  domain/         plain dataclasses passed between layers
  repositories/   all SQL, every query scoped by bot_id / owner_id
  rag/
    chunking/     Chunker strategies + registry/factory
    embeddings/   Voyage / hash adapters + LRU cache decorator
    vectorstores/ VectorStore port + Chroma adapter
    retrieval/    vector, keyword, hybrid (composite) + RRF fusion
    generation/   prompt builder, Claude adapter, citations
  ingest/         loaders, SSRF-safe crawler, upload validation, pipeline
  services/       chat, ingestion, analytics, rate limiting
  routers/        thin HTTP layer
  container.py    composition root (dependency injection)
  worker.py       arq background jobs
api/evals/        retrieval eval harness (BM25 + vector indexes, metrics)
web/              Next.js dashboard, playground, analytics, embeddable widget
```
