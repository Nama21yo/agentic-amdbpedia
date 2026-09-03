# agentic-amdbpedia frontend (starter)

The web UI for the "prepare a mapping for this infobox" workflow: SvelteKit 5

- TypeScript + Tailwind v4, scaffolded with `sv create` and installed with
  pnpm. Not built from, but structurally _and visually_ inspired by
  `vercel/ai-chatbot-svelte` — its streaming-chat shape and shadcn-svelte
  design language, without the Vercel-specific pieces (Postgres/Neon chat
  history, Blob storage, provider-routed AI SDK calls, auth) that don't
  apply here.

## What's real vs. planned

The UI, routing, and API client are real and functional. As of
implementation.md Phase 2 Milestone 16, every `cross-lingual`-side endpoint
this frontend calls now exists on the real backend
(`mcp_server/http_app.py`, run with `uvicorn mcp_server.http_app:app`
alongside the MCP stdio server) — only `getCoverageStats`, which talks to
`agentic-dbpedia`'s own statistics service, remains unconfirmed against
this client. Each API function in `src/lib/api.ts` is still labeled
`PLANNED` or `EXISTING` in its doc comment for whichever endpoints haven't
caught up yet. A screen whose endpoint isn't reachable fails closed into a
visible "not reachable yet" message instead of crashing or showing fake
data — that's intentional, not a bug to fix later.

| Screen                       | Calls                                           | Status                                                                             |
| ---------------------------- | ----------------------------------------------- | ---------------------------------------------------------------------------------- |
| Mapping Assistant (`/`)      | `cross-lingual` `POST /v1/preview` (SSE)        | **Exists** — `mcp_server/http_app.py`, refs implementation.md 16.3                 |
| Mapping Assistant chat panel | `cross-lingual` `/v1/find-semantic-match`       | **Exists** — refs implementation.md 16.3                                           |
| Review Queue (`/review`)     | `cross-lingual` `GET /v1/reviews`               | **Exists** — `mcp_server/http_app.py`, refs implementation.md 14.1                 |
| Review Queue (`/review`)     | `cross-lingual` `POST /v1/reviews/:id/decision` | **Exists** — refs implementation.md 14.2/14.3 (correction + publish support)       |
| Coverage (`/coverage`)       | `agentic-dbpedia` `/api/statistics/summary`     | Backend route exists already; response shape not yet confirmed against this client |

## Human-in-the-loop review

The Review Queue (`/review`) is where a reviewer actually corrects the
mapping agent's predictions, not just accepts or rejects them blindly:

- Expand any queued item to edit its mappings directly — `templateProperty`,
  `ontologyProperty`, and add/remove rows entirely
  (`src/lib/components/MappingEditor.svelte`). An edited row is diff
  -highlighted against the model's original prediction, with a one-click
  reset back to it.
- Each row has a **suggest** panel that calls the same
  `find_semantic_match` retrieval endpoint the chat panel uses, so a
  correction is picked from real grounded candidates instead of freehand
  -typed (and possibly misspelled) — consistent with the rest of this
  project's "never let free text stand in for retrieval" stance.
- A row a reviewer edits is treated as human-confirmed (`confidence` snaps
  to 100%); the backend logs `was_correction: true` for it in the training
  log whenever the final `ontologyProperty` differs from what the model
  predicted, regardless of whether the item is later published.
- Publishing is a separate, explicit opt-in (checkbox + a confirmation
  dialog that lists exactly what will be written) layered on top of
  approval — never implied by clicking Approve. A failed publish (e.g. no
  MediaWiki credentials configured) is surfaced with the real server
  message via `DecisionFailedError` (`src/lib/api.ts`), not treated like a
  generic unreachable-backend error — the review decision itself still
  lands even when the publish half fails.

## Auth

Deliberately skipped for this iteration — no auth headers, no login flow.
This is an internal tool for a small set of maintainers; add a shared token
or real auth once that becomes a problem, not before.

## Component library

Uses the same stack `ai-chatbot-svelte` does: **shadcn-svelte** primitives
(`src/lib/components/ui/*` — button, input, textarea, label, card, badge,
table, checkbox, separator, tooltip, alert-dialog, skeleton, sonner) built
on **Bits UI**, styled with Tailwind v4's CSS-variable theme
(`src/routes/layout.css`, "new-york" style, neutral base color) plus
**`mode-watcher`** for a real light/dark toggle and **`@lucide/svelte`**
for icons. The shadcn-svelte CLI's newer `init` flow requires an
interactive TTY to pick a design-system preset (confirmed: piped stdin is
ignored outright, so it can't be scripted) — these files were hand-authored
to match its actual generated output instead of fought into working
non-interactively; `pnpm dlx shadcn-svelte@latest add <name>` should still
work against `components.json` for adding more.

App-specific composites live one level up in `src/lib/components/`
(`AppSidebar`, `ModeToggle`, `StatusBadge`, `ConfidencePill`, `StepTracker`,
`MappingEditor`) rather than copy-pasted per page.

## Running it

```bash
pnpm install
cp .env.example .env   # point at your local backends, or leave the defaults
pnpm run dev --open
```

`pnpm run check` runs `svelte-check`; `pnpm run lint` / `pnpm run format`
wrap prettier + eslint, both already configured by `sv create`.
