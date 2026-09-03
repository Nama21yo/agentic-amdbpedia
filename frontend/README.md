# agentic-amdbpedia frontend

The web UI for the Amharic infobox → DBpedia mapping workflow: SvelteKit 5,
TypeScript, Tailwind v4, scaffolded with `sv create` and installed with pnpm.

## What's real vs. planned

The UI, routing, and API client are real and functional, and every endpoint
this frontend calls lives on `agentic-amdbpedia`'s own backend
(`mcp_server/http_app.py`, run with `uvicorn mcp_server.http_app:create_app
--factory` alongside the MCP stdio server) — this frontend has no remaining
dependency on `agentic-dbpedia` at all. `getCoverageStats` used to call
`agentic-dbpedia`'s `/api/statistics/summary`, an endpoint that (found live)
never actually existed there; it's since moved to `GET
{CROSS_LINGUAL_URL}/v1/coverage`, computed from this repo's own review
queue (`db/session.py::coverage_stats`) rather than depending on a
DEF-extraction-output crawl. A screen whose endpoint isn't reachable fails
closed into a visible "not reachable yet" message instead of crashing or
showing fake data — that's intentional, not a bug to fix later.

| Screen                   | Calls                                           | Status                                                                       |
| ------------------------ | ----------------------------------------------- | ---------------------------------------------------------------------------- |
| Chat (`/`)               | `cross-lingual` `POST /v1/preview` (SSE)        | **Exists** — `mcp_server/http_app.py`, refs implementation.md 16.3           |
| Chat (`/`)               | `cross-lingual` `POST /v1/find-semantic-match`  | **Exists** — refs implementation.md 16.3                                     |
| Review Queue (`/review`) | `cross-lingual` `GET /v1/reviews`               | **Exists** — `mcp_server/http_app.py`, refs implementation.md 14.1           |
| Review Queue (`/review`) | `cross-lingual` `POST /v1/reviews/:id/decision` | **Exists** — refs implementation.md 14.2/14.3 (correction + publish support) |
| Coverage (`/coverage`)   | `cross-lingual` `GET /v1/coverage`              | **Exists** — `mcp_server/http_app.py` + `db/session.py::coverage_stats`      |

## Chat (`/`)

One conversation, one input — pasting an infobox and asking about a single
field are the same box, not two separate panels. Input starting with
`{{Infobox` (case-insensitive) runs the full extract → predict → format →
persist pipeline over SSE, streaming each node's progress inline as part of
the assistant's turn; anything else runs a quick grounded lookup
(`find_semantic_match`) instead. Every pipeline run also lands in the
Review Queue regardless of what's shown here — this page is a preview, not
the approval step.

## Human-in-the-loop review

The Review Queue (`/review`) is where a reviewer actually corrects the
mapping agent's predictions, not just accepts or rejects them blindly:

- Expand any queued item to edit its mappings directly — `templateProperty`,
  `ontologyProperty`, and add/remove rows entirely
  (`src/lib/components/MappingEditor.svelte`). An edited row is diff
  -highlighted against the model's original prediction, with a one-click
  reset back to it.
- Each row has a **suggest** panel that calls the same
  `find_semantic_match` retrieval endpoint the chat uses, so a correction
  is picked from real grounded candidates instead of freehand-typed (and
  possibly misspelled) — consistent with the rest of this project's "never
  let free text stand in for retrieval" stance.
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

**shadcn-svelte** primitives (`src/lib/components/ui/*` — button, input,
textarea, label, card, badge, table, checkbox, separator, tooltip,
alert-dialog, skeleton, sonner) built on **Bits UI**, styled with Tailwind
v4's CSS-variable theme (`src/routes/layout.css`, "new-york" style, a
warm neutral palette with its own accent color, tuned for both light and
dark) plus **`mode-watcher`** for a real light/dark toggle and
**Font Awesome** (`svelte-fa` + `@fortawesome/free-solid-svg-icons`) for
icons — kept to the small set that actually clarifies a control's purpose
(search, remove, restore, add, spinner, status, nav), not decorative ones.
The shadcn-svelte CLI's newer `init` flow requires an interactive TTY to
pick a design-system preset (confirmed: piped stdin is ignored outright,
so it can't be scripted) — these files were hand-authored to match its
actual generated output instead of fought into working non-interactively;
`pnpm dlx shadcn-svelte@latest add <name>` should still work against
`components.json` for adding more.

App-specific composites live one level up in `src/lib/components/`
(`AppSidebar`, `ModeToggle`, `StatusBadge`, `ConfidencePill`, `StepTracker`,
`MappingEditor`) rather than copy-pasted per page.

## Running it

```bash
pnpm install
cp .env.example .env   # point at your local backend, or leave the default
pnpm run dev --open
```

`pnpm run check` runs `svelte-check`; `pnpm run lint` / `pnpm run format`
wrap prettier + eslint, both already configured by `sv create`. `pnpm run
test` runs Vitest (`@testing-library/svelte` + jsdom) for actual component
-level reactivity tests -- `src/lib/chat-history.test.ts` mounts
`AppSidebar.svelte` for real and drives the chat-history store to prove the
sidebar's "Chats" list genuinely updates live, not just that the store
functions run without throwing.
