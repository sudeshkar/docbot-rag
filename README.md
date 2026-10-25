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
cp .env.example .env        # set an LLM key (see below) and a long random JWT_SECRET
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

Generate a `JWT_SECRET` with `python -c "import secrets; print(secrets.token_urlsafe(48))"` and paste the output into `.env`.

### Choosing an LLM provider

Chat answers come from either Claude (the default) or Groq. Embeddings are a separate setting: `EMBEDDING_PROVIDER=voyage` needs a `VOYAGE_API_KEY`, and `EMBEDDING_PROVIDER=hash` works offline with no key (lower retrieval quality).

**Claude:** set `ANTHROPIC_API_KEY` in `api/.env`. That's all; `LLM_PROVIDER=anthropic` is the default.

**Groq** (has a free tier, so the whole app can run on one free key):

1. Create a key at [console.groq.com/keys](https://console.groq.com/keys).
2. In `api/.env`, set:

   ```env
   LLM_PROVIDER=groq
   GROQ_API_KEY=gsk_...
   GROQ_MODEL=openai/gpt-oss-120b
   EMBEDDING_PROVIDER=hash      # or voyage, with VOYAGE_API_KEY
   ```

   `ANTHROPIC_API_KEY` and `VOYAGE_API_KEY` can stay empty.
3. Restart uvicorn so it reloads `.env`. The worker doesn't call the LLM, so it doesn't need a restart.
4. Ask a question in the Playground.

Groq retires models from time to time. If chat fails and the API log shows `model_not_found`, list the models your key can use and put one of them in `GROQ_MODEL`:

```bash
curl -s https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY"
```

When chat shows "The assistant is temporarily unavailable", the uvicorn terminal logs the real cause (`LLM call failed: ...`). On Groq, the usual ones are `401` (wrong key), `404` (retired model) and `429` (free-tier rate limit; wait a minute). Open-weight models follow the citation rules less strictly than Claude, so expect the occasional answer without `[n]` citations.

Try it with `sample_docs/acme-help-center.md`, or the three Brewly files in `sample_docs/brewly/` (Markdown and plain text) to test answers that span several documents. To try the widget on a separate site, put your widget key in `sample_docs/widget-test.html`, add `http://localhost:5500` under the bot's allowed websites, and serve it with `python -m http.server 5500` from `sample_docs/`. Embed the widget on any page with:

```html
<script src="http://localhost:3000/widget.js" data-key="pk_..." async></script>
```

## Deploying for free

Everything runs on one free server, behind one domain: Caddy sends `https://<domain>/api/*` to FastAPI and everything else to Next.js. Keeping the dashboard and API on the same origin is what lets the login session be a first-party, `SameSite=Strict`, httpOnly cookie. Split across two domains (e.g. Vercel + a separate API host), browsers that block third-party cookies would break login. The API and the worker also have to share a disk, since the worker reads the files the API saves.

| Part | Where |
|---|---|
| Web app, API, worker, Postgres, Chroma, Redis, HTTPS (Caddy) | Oracle Cloud Always Free VM (`VM.Standard.A1.Flex`, Ubuntu) |
| Domain | DuckDNS, e.g. `docbot.duckdns.org` |
| Chat / embeddings | Groq free tier / `EMBEDDING_PROVIDER=hash` (or Voyage) |

**On the server:**

1. Install Docker, and open ports 80 and 443 in the Oracle security list and the VM firewall.
2. Point your DuckDNS name at the server's public IP.
3. Clone the repo and create the two settings files. Generate every secret with `python3 -c "import secrets; print(secrets.token_hex(32))"`.

   ```bash
   cp .env.prod.example .env          # APP_DOMAIN, POSTGRES_PASSWORD, REDIS_PASSWORD
   cp api/.env.example api/.env       # LLM keys and JWT_SECRET (CORS is set from APP_DOMAIN)
   chmod 600 .env api/.env            # secrets readable by your user only
   ```

4. Start everything. Migrations run automatically, and Caddy gets the HTTPS certificate on first start.

   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   curl https://<APP_DOMAIN>/api/health
   ```

5. Open `https://<APP_DOMAIN>`, sign up, and add your sites under each bot's **Embed > Allowed websites**.

To update later: `git pull && docker compose -f docker-compose.prod.yml up -d --build`.

**What the production stack enforces:**

- Only Caddy is reachable from the internet (ports 80/443). Postgres, Chroma, Redis, the API and the web app sit on the internal Docker network.
- **Sessions:** the login token lives only in an `httpOnly; Secure; SameSite=Strict` cookie, so page scripts (or an XSS) can't read it. Cookie-authenticated writes also need an `X-DocBot-CSRF` header, which cross-site forms can't send. API clients can still use `Authorization: Bearer`.
- **Widget embedding:** `/embed/<key>` is served with `Content-Security-Policy: frame-ancestors <the bot's allowed websites>`, so browsers refuse to show the widget on any other site. The iframe reads its embedding page from `location.ancestorOrigins` where available instead of trusting `?origin=`. A bot with no allowlist can be embedded anywhere.
- **Input:** plain-text fields reject HTML tags and are stripped of control and bidi characters. Chat answers render without raw HTML, links must be http(s)/mailto, and images are dropped.
- The API refuses to start with a missing, default or short (< 32 characters) `JWT_SECRET`.
- Passwords are bcrypt-hashed. Rate-limit keys are stored in Redis as HMAC-SHA256 digests, never as raw client IPs.
- Redis requires a password. Postgres uses a generated password instead of the dev default.
- Containers run as non-root users, and secrets are never baked into images (`.dockerignore`).
- HTTPS with HSTS, a 25 MB request cap at the proxy, and server-software headers removed.

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
