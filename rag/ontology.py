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

        curie = local_name if ":" in local_name else f"dbo:{local_name}"

        return OntologyProperty(
            local_name=local_name,
            curie=curie,
            uri=cls._property_uri(curie),
            label=label,
            property_type=property_type,
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
    """Existing Amharic templateProperty -> ontologyProperty mappings."""

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

    def __init__(self, mappings: dict[str, ExistingTemplateMapping]) -> None:
        self._mappings = mappings

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

        for match in cls.PROPERTY_MAPPING_RE.finditer(text):
            body = match.group("body")
            template_match = cls.TEMPLATE_PROPERTY_RE.search(body)
            ontology_match = cls.ONTOLOGY_PROPERTY_RE.search(body)
            if template_match is None or ontology_match is None:
                continue

            template_property = cls._clean_mapping_value(template_match.group("value"))
            ontology_property = cls._clean_mapping_value(ontology_match.group("value"))
            if not template_property or not ontology_property:
                continue

            mappings.setdefault(
                cls._normalize_template_property(template_property),
                ExistingTemplateMapping(
                    template_property=template_property,
                    ontology_property=ontology_property,
                ),
            )

        log_event(LOGGER, "mapping_index.load_completed", mappings=len(mappings))
        return cls(mappings)

    def lookup(self, template_property: str) -> ExistingTemplateMapping | None:
        return self._mappings.get(self._normalize_template_property(template_property))

    @staticmethod
    def _clean_mapping_value(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _normalize_template_property(value: str) -> str:
        normalized = re.sub(r"\s+", "_", value.strip())
        return normalized.strip("_").casefold()
