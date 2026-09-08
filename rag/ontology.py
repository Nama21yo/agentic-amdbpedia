"""DBpedia ontology property catalog and existing Amharic mapping index.

Ported from agentic-dbpedia's `services/ontology.py` (refs implementation.md
10.1). Both classes parse the cached MediaWiki XML exports that already ship
in `data/wiki_cache/` — `ontology.xml` (the `OntologyClass:`/
`OntologyProperty:` namespace) and `mapping_am.xml` (the `Mapping am:*`
namespace). Kept dependency-light and decoupled from any web-framework
settings object, unlike the original, so it can be imported standalone here.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from errors import RetrievalUnavailableError
from logging_config import log_event

LOGGER = logging.getLogger("dbpedia_mapping_assistant.ontology")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ONTOLOGY_XML = PROJECT_ROOT / "data" / "wiki_cache" / "ontology.xml"
DEFAULT_MAPPING_AM_XML = PROJECT_ROOT / "data" / "wiki_cache" / "mapping_am.xml"


@dataclass(frozen=True, slots=True)
class OntologyProperty:
    local_name: str
    curie: str
    uri: str
    label: str
    property_type: str  # "ObjectProperty" | "DatatypeProperty" | "Property"
    # rdfs:domain as declared on the property page, e.g. "Airport" — many real
    # properties have none (reused across classes) or a broad domain like
    # "owl:Thing"/"Place", so retrieval treats this as a soft ranking signal,
    # never a hard filter (refs 10.3).
    domain: str | None = None

    @property
    def search_text(self) -> str:
        return f"{self.label} {self.local_name} {self.curie}"


@dataclass(frozen=True, slots=True)
class ExistingTemplateMapping:
    template_property: str
    ontology_property: str


class DbpediaOntologyCatalog:
    """All DBpedia ontology properties, parsed from a cached wiki export."""

    LABEL_RE = re.compile(r"\{\{\s*label\s*\|\s*en\s*\|\s*([^}|]+)", re.IGNORECASE)
    DOMAIN_RE = re.compile(r"\|\s*rdfs:domain\s*=\s*([^\n|}]+)", re.IGNORECASE)
    PREFIX_URIS = {
        "dbo": "http://dbpedia.org/ontology/",
        "foaf": "http://xmlns.com/foaf/0.1/",
        "dc": "http://purl.org/dc/elements/1.1/",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    }

    def __init__(self, properties: list[OntologyProperty]) -> None:
        if not properties:
            raise RetrievalUnavailableError("DBpedia ontology catalog is empty")

        self.properties = properties
        self._by_name: dict[str, OntologyProperty] = {}
        for prop in properties:
            self._by_name[self._normalize_property_name(prop.local_name)] = prop
            self._by_name[self._normalize_property_name(prop.curie)] = prop

    @classmethod
    def from_default_cache(cls) -> DbpediaOntologyCatalog:
        return cls.from_ontology_xml(DEFAULT_ONTOLOGY_XML)

    @classmethod
    def from_ontology_xml(cls, ontology_path: Path) -> DbpediaOntologyCatalog:
        if not ontology_path.is_file():
            raise RetrievalUnavailableError(f"DBpedia ontology XML not found: {ontology_path}")

        log_event(LOGGER, "ontology.load_started", ontology_path=str(ontology_path))

        properties: list[OntologyProperty] = []
        try:
            for _event, elem in ET.iterparse(ontology_path, events=("end",)):
                if cls._local_name(elem.tag) != "page":
                    continue

                prop = cls._property_from_page(elem)
                elem.clear()
                if prop is not None:
                    properties.append(prop)
        except (ET.ParseError, OSError, UnicodeDecodeError) as exc:
            raise RetrievalUnavailableError(
                f"Could not load ontology XML {ontology_path}: {exc}"
            ) from exc

        log_event(LOGGER, "ontology.load_completed", properties=len(properties))
        return cls(properties)

    def find(self, name: str) -> OntologyProperty | None:
        return self._by_name.get(self._normalize_property_name(name))

    @classmethod
    def _property_from_page(cls, page_el: ET.Element) -> OntologyProperty | None:
        title = cls._first_text(page_el, "title") or ""
        if not title.startswith("OntologyProperty:"):
            return None

        wiki_name = title.split(":", 1)[1].strip()
        local_name = cls._wiki_title_to_property_name(wiki_name)
        text = cls._first_text(page_el, "text") or ""
        label = cls._extract_english_label(text) or cls._humanize_property_name(local_name)
        property_type = cls._extract_property_type(text)
        domain = cls._extract_domain(text)

        curie = local_name if ":" in local_name else f"dbo:{local_name}"

        return OntologyProperty(
            local_name=local_name,
            curie=curie,
            uri=cls._property_uri(curie),
            label=label,
            property_type=property_type,
            domain=domain,
        )

    @classmethod
    def _extract_english_label(cls, text: str) -> str | None:
        match = cls.LABEL_RE.search(text)
        if not match:
            return None
        return re.sub(r"\s+", " ", match.group(1)).strip()

    @staticmethod
    def _extract_property_type(text: str) -> str:
        if re.search(r"\{\{\s*ObjectProperty\b", text, flags=re.IGNORECASE):
            return "ObjectProperty"
        if re.search(r"\{\{\s*DatatypeProperty\b", text, flags=re.IGNORECASE):
            return "DatatypeProperty"
        return "Property"

    @classmethod
    def _extract_domain(cls, text: str) -> str | None:
        match = cls.DOMAIN_RE.search(text)
        if not match:
            return None
        value = match.group(1).strip()
        if value.casefold() == "owl:thing":
            # "applies to any class" carries no useful filtering signal.
            return None
        # Local class name only, matching how OntologyClass:/target_class values
        # are already spelled elsewhere (e.g. "Airport", not "dbo:Airport").
        if ":" in value:
            value = value.split(":", 1)[1]
        return value or None

    @staticmethod
    def _wiki_title_to_property_name(name: str) -> str:
        if not name:
            return name
        return f"{name[0].lower()}{name[1:]}"

    @staticmethod
    def _humanize_property_name(name: str) -> str:
        spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", name)
        return spaced.replace("_", " ").strip().lower()

    @staticmethod
    def _normalize_property_name(name: str) -> str:
        value = name.strip()
        if value.startswith("dbo:"):
            value = value.split(":", 1)[1]
        if value.startswith("http://dbpedia.org/ontology/"):
            value = value.rsplit("/", 1)[1]
        return value.casefold()

    @classmethod
    def _property_uri(cls, curie: str) -> str:
        if ":" not in curie:
            return f"http://dbpedia.org/ontology/{curie}"
        prefix, local_name = curie.split(":", 1)
        base_uri = cls.PREFIX_URIS.get(prefix)
        return f"{base_uri}{local_name}" if base_uri else curie

    @staticmethod
    def _first_text(element: ET.Element, local_name: str) -> str | None:
        for child in element.iter():
            if DbpediaOntologyCatalog._local_name(child.tag) == local_name:
                return "".join(child.itertext())
        return None

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1] if "}" in tag else tag


class AmharicMappingIndex:
    """Existing Amharic templateProperty -> ontologyProperty mappings.

    Also tracks the set of template (page) names the corpus has a real
    `Mapping am:<name>` page for -- `mcp_server.pipeline._is_infobox_like`'s
    marker-word heuristic ("infobox"/"info box"/"መረጃ"/"ሳጥን") misses real,
    already-mapped templates whose Amharic name doesn't happen to contain
    one of those words (confirmed live: "የቦታ ስም", the Place template, has
    none of them). `is_known_template` gives the pipeline a second,
    ground-truth signal -- a template this corpus already has a mapping
    page for is unambiguously a real infobox, regardless of what its name
    looks like.

    `lookup()` matches a templateProperty globally, first-page-wins across
    the whole corpus -- kept exactly as before for existing callers. But
    common Amharic field names (ስም, ስዕል, ከፍታ, ...) genuinely get reused
    across unrelated templates with different intended ontology properties,
    and confirmed live that `lookup()`'s global, unscoped match makes
    `mcp_server.pipeline._extract_node` silently treat a brand-new field on
    an unmapped template (e.g. Dam's own "ከፍታ") as "already published"
    just because some *other*, unrelated template (Place) happens to use
    the same Amharic word for a different property (elevation, not
    height) -- dropping the field before it ever reaches prediction, on a
    template this corpus has never actually mapped at all.
    `is_already_mapped_on_template()` is the scoped alternative:
    template-and-property together, no cross-template fallback, so a
    field only counts as "already published" when it actually is, for
    *this* template.
    """

    PROPERTY_MAPPING_RE = re.compile(
        r"\{\{\s*PropertyMapping\b(?P<body>.*?)\}\}",
        re.IGNORECASE | re.DOTALL,
    )
    TEMPLATE_PROPERTY_RE = re.compile(
        r"\|\s*templateProperty\s*=\s*(?P<value>[^|}\n]+)", re.IGNORECASE
    )
    ONTOLOGY_PROPERTY_RE = re.compile(
        r"\|\s*ontologyProperty\s*=\s*(?P<value>[^|}\n]+)", re.IGNORECASE
    )
    # `scripts.refresh_wiki_cache.refresh_mappings` re-serializes a merged
    # export through ElementTree, which rewrites the default `xmlns=` into
    # an explicit `ns0:` prefix on every element (confirmed live) -- the
    # freshly-cached file after any `just refresh-mappings` run no longer
    # has bare `<page>`/`<title>` tags the way the original raw API export
    # (and this repo's shipped `data/wiki_cache/mapping_am.xml` snapshot)
    # does. An optional namespace prefix keeps both forms working.
    PAGE_TITLE_RE = re.compile(
        r"<(?:[\w.-]+:)?title>\s*Mapping\s+am:(?P<name>[^<]+?)\s*</(?:[\w.-]+:)?title>",
        re.IGNORECASE,
    )
    # MediaWiki XML export pages never nest, so splitting on the literal
    # page-boundary tags is enough to scope each PropertyMapping match to
    # the page (template) it actually came from, without a full XML parse.
    PAGE_RE = re.compile(
        r"<(?:[\w.-]+:)?page\b.*?</(?:[\w.-]+:)?page>", re.IGNORECASE | re.DOTALL
    )

    def __init__(
        self,
        mappings: dict[str, ExistingTemplateMapping],
        template_names: frozenset[str] = frozenset(),
        scoped_mappings: dict[tuple[str, str], ExistingTemplateMapping] | None = None,
    ) -> None:
        self._mappings = mappings
        self._template_names = template_names
        self._scoped_mappings: dict[tuple[str, str], ExistingTemplateMapping] = (
            scoped_mappings or {}
        )

    def __len__(self) -> int:
        return len(self._mappings)

    @classmethod
    def from_default_cache(cls) -> AmharicMappingIndex:
        return cls.from_mapping_xml(DEFAULT_MAPPING_AM_XML)

    @classmethod
    def from_mapping_xml(cls, mapping_path: Path) -> AmharicMappingIndex:
        if not mapping_path.is_file():
            log_event(LOGGER, "mapping_index.missing", mapping_path=str(mapping_path))
            return cls({})

        log_event(LOGGER, "mapping_index.load_started", mapping_path=str(mapping_path))
        text = mapping_path.read_text(encoding="utf-8")
        mappings: dict[str, ExistingTemplateMapping] = {}
        scoped_mappings: dict[tuple[str, str], ExistingTemplateMapping] = {}
        template_names: set[str] = set()

        for page_match in cls.PAGE_RE.finditer(text):
            page_text = page_match.group()
            title_match = cls.PAGE_TITLE_RE.search(page_text)
            if title_match is None:
                continue
            normalized_template_name = cls._normalize_template_name(title_match.group("name"))
            template_names.add(normalized_template_name)

            for match in cls.PROPERTY_MAPPING_RE.finditer(page_text):
                body = match.group("body")
                template_match = cls.TEMPLATE_PROPERTY_RE.search(body)
                ontology_match = cls.ONTOLOGY_PROPERTY_RE.search(body)
                if template_match is None or ontology_match is None:
                    continue

                template_property = cls._clean_mapping_value(template_match.group("value"))
                ontology_property = cls._clean_mapping_value(ontology_match.group("value"))
                if not template_property or not ontology_property:
                    continue

                entry = ExistingTemplateMapping(
                    template_property=template_property,
                    ontology_property=ontology_property,
                )
                normalized_property = cls._normalize_template_property(template_property)
                mappings.setdefault(normalized_property, entry)
                scoped_mappings.setdefault(
                    (normalized_template_name, normalized_property), entry
                )

        log_event(
            LOGGER,
            "mapping_index.load_completed",
            mappings=len(mappings),
            templates=len(template_names),
        )
        return cls(mappings, frozenset(template_names), scoped_mappings)

    def lookup(self, template_property: str) -> ExistingTemplateMapping | None:
        return self._mappings.get(self._normalize_template_property(template_property))

    def is_already_mapped_on_template(
        self, template_name: str, template_property: str
    ) -> ExistingTemplateMapping | None:
        """Scoped alternative to `lookup()`: only counts as already-mapped
        when *this exact template* has a published mapping for the field --
        never a coincidental match from some other, unrelated template. See
        this class's docstring for why `lookup()` alone isn't safe for
        `mcp_server.pipeline._extract_node`'s "skip already-published
        fields" filter."""

        return self._scoped_mappings.get(
            (
                self._normalize_template_name(template_name),
                self._normalize_template_property(template_property),
            )
        )

    def is_known_template(self, template_name: str) -> bool:
        """Whether this corpus has a real `Mapping am:<template_name>` page
        -- a stronger, ground-truth signal than the marker-word heuristic
        `_is_infobox_like` uses on its own."""

        return self._normalize_template_name(template_name) in self._template_names

    def all_mappings(self) -> tuple[ExistingTemplateMapping, ...]:
        return tuple(self._mappings.values())

    @staticmethod
    def _clean_mapping_value(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _normalize_template_property(value: str) -> str:
        normalized = re.sub(r"\s+", "_", value.strip())
        return normalized.strip("_").casefold()

    @staticmethod
    def _normalize_template_name(value: str) -> str:
        normalized = re.sub(r"[\s_]+", " ", value.strip())
        return normalized.casefold()
