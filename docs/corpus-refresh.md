# Corpus refresh

`scripts/refresh_wiki_cache.py` (refs implementation.md 12.1) pulls the live
`OntologyClass:`/`OntologyProperty:` and `Mapping am:*` namespaces from
mappings.dbpedia.org into `data/wiki_cache/ontology.xml` and
`data/wiki_cache/mapping_am.xml`. `rag/ontology.py`'s parsers read those
files unchanged, and `rag/corpus.py::build_corpus()` merges the result into
the retrieval corpus — refreshing never requires a code change anywhere
downstream.

## Manual runs

```bash
just refresh-ontology   # OntologyClass: + OntologyProperty: (namespaces 200/202)
just refresh-mappings   # Mapping am:* (namespace 390)
```

Both leave the existing cached file untouched (not truncated) if the run
fails partway through — safe to run at any time, including in CI, without
risking the committed seed data.

## Recommended schedule

The ontology changes rarely (new DBpedia ontology properties are added on
the order of weeks); Amharic mappings change far more often, since that's
exactly the page contributors actively edit. Two different cadences,
matching that:

| Target | Cadence | Rationale |
|---|---|---|
| `just refresh-ontology` | daily | Low page-count churn; a daily pull is already more current than the 2+ year old seed data this replaced. |
| `just refresh-mappings` | every 15–30 min | Contributors publish new `Mapping am:*` pages through this same system (M14's review queue) — a short poll keeps newly-published aliases available to retrieval quickly. |

Example crontab (adjust `WORKDIR` to the actual deployment checkout path):

```cron
# Ontology: once a day at 03:17 (avoid the top of the hour)
17 3 * * *   cd WORKDIR && just refresh-ontology  >> data/wiki_cache/refresh.log 2>&1

# Amharic mappings: every 20 minutes
*/20 * * * * cd WORKDIR && just refresh-mappings  >> data/wiki_cache/refresh.log 2>&1
```

A systemd timer or any other scheduler works the same way — both `just`
targets are plain, idempotent, zero-argument commands with a real exit code
(0 on success, 1 if the fetch failed and the cache was left untouched), so
they compose with whatever scheduling/alerting infrastructure a deployment
already uses.

## Eager refresh after publish

Milestone 14.3 (consent-gated MediaWiki publish) calls
`refresh_mappings()` directly right after a successful publish, so a
contributor's own new mapping becomes visible to retrieval immediately
rather than waiting for the next scheduled poll. That hook doesn't exist
yet — 14.3 wires it once publishing itself exists — but `refresh_mappings()`
is already a plain importable function (`from scripts.refresh_wiki_cache
import refresh_mappings`) specifically so that wiring is a single function
call, not new plumbing.

## Verifying a refresh worked

```bash
uv run python -c "
from rag.ontology import DbpediaOntologyCatalog, AmharicMappingIndex
print('ontology properties:', len(DbpediaOntologyCatalog.from_default_cache().properties))
print('amharic mappings:', len(AmharicMappingIndex.from_default_cache()))
"
```
