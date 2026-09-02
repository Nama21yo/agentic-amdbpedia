# agentic-amdbpedia frontend (starter)

The web UI for the "prepare a mapping for this infobox" workflow: SvelteKit 5

- TypeScript + Tailwind v4, scaffolded with `sv create` and installed with
  pnpm. Not built from, but structurally inspired by, `vercel/ai-chatbot-svelte`
  — its streaming-chat shape, without the Vercel-specific pieces (Postgres/Neon
  chat history, Blob storage, provider-routed AI SDK calls) that don't apply
  here.

## What's real vs. planned

This is a starter, not a finished product. The UI, routing, and API client
are real and functional; most of the endpoints they call are **not yet
implemented on the backend**. Each API function in `src/lib/api.ts` is
labeled `PLANNED` or `EXISTING` in its doc comment. Until the planned
endpoints exist, every screen fails closed into a visible "not reachable
yet" message instead of crashing or showing fake data — that's intentional,
not a bug to fix later.

| Screen                       | Calls                                           | Status                                                                             |
| ---------------------------- | ----------------------------------------------- | ---------------------------------------------------------------------------------- |
| Mapping Assistant (`/`)      | `agentic-dbpedia` `/api/v2/agent/preview` (SSE) | Planned                                                                            |
| Mapping Assistant chat panel | `cross-lingual` `/v1/find-semantic-match`       | Planned — cross-lingual is currently MCP-stdio only                                |
| Review Queue (`/review`)     | `cross-lingual` `GET /v1/reviews`               | **Exists** — `mcp_server/http_app.py`, refs implementation.md 14.1                 |
| Review Queue (`/review`)     | `cross-lingual` `POST /v1/reviews/:id/decision` | **Exists** — refs implementation.md 14.2/14.3 (correction + publish support)       |
| Coverage (`/coverage`)       | `agentic-dbpedia` `/api/statistics/summary`     | Backend route exists already; response shape not yet confirmed against this client |

## Auth

Deliberately skipped for this iteration — no auth headers, no login flow.
This is an internal tool for a small set of maintainers; add a shared token
or real auth once that becomes a problem, not before.

## Component library

Hand-built Tailwind, not shadcn-svelte/Bits UI. `ai-chatbot-svelte` uses
those; wiring up the shadcn-svelte CLI is a reasonable follow-up if the team
wants that exact look, but wasn't pulled in for this starter to keep the
first commit small.

## Running it

```bash
pnpm install
cp .env.example .env   # point at your local backends, or leave the defaults
pnpm run dev --open
```

`pnpm run check` runs `svelte-check`; `pnpm run lint` / `pnpm run format`
wrap prettier + eslint, both already configured by `sv create`.
