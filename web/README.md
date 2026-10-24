# DocBot web

Next.js dashboard, playground, analytics and the embeddable chat widget (`public/widget.js`, `/embed/[key]`).

```bash
cp .env.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev                  # http://localhost:3000
npm test                     # Vitest unit tests for SSE parsing, citations, chart layout, formatting
```

See the [project README](../README.md) for the full setup.
