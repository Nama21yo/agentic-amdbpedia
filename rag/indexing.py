"""Index DBpedia ontology property documents into Qdrant."""

from __future__ import annotations

import argparse
import json
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import Settings
from rag.embeddings import (
    DEFAULT_DENSE_VECTOR_SIZE,
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
    DenseEmbedder,
    SparseEmbedder,
    embed_dense,
    embed_sparse,
    qdrant_sparse_vector,
)
from scripts.validate_corpus import parse_property_documents, validate_corpus

DEFAULT_COLLECTION_NAME = "dbpedia_ontology_properties"
CHUNK_NAMESPACE = uuid.UUID("65da7e5a-ad87-4a72-a38c-6fbdf08edcb5")


@dataclass(frozen=True)
class OntologyChunk:
    """A single indexable ontology property proposition."""

    chunk_id: str
    text: str
    payload: dict[str, Any]

    @property
    def embedding_text(self) -> str:
        aliases = " ".join(str(alias) for alias in self.payload["amharic_aliases"])
        english_aliases = " ".join(str(alias) for alias in self.payload["english_aliases"])
        return f"{self.text} | Aliases: {aliases} | Keywords: {english_aliases}"


def _split_aliases(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _load_alias_rows(data_dir: Path) -> list[dict[str, Any]]:
    payload = json.loads((data_dir / "aliases.json").read_text(encoding="utf-8"))
    aliases = payload.get("aliases", [])
    if not isinstance(aliases, list):
        return []
    return [row for row in aliases if isinstance(row, dict)]


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _chunk_id(class_name: str, property_name: str) -> str:
    return str(uuid.uuid5(CHUNK_NAMESPACE, f"{class_name}:{property_name}"))


def chunk_corpus(data_dir: Path | str = "data") -> list[OntologyChunk]:
    """Parse corpus markdown into deterministic metadata-enriched chunks."""

    corpus_dir = Path(data_dir)
    validate_corpus(corpus_dir)
    alias_rows = _load_alias_rows(corpus_dir)
    chunks: list[OntologyChunk] = []

    for path in sorted(corpus_dir.glob("*.md")):
        for document in parse_property_documents(path):
            fields = document.fields
            property_name = fields["propertyName"]
            row_aliases = [
                str(row["amharic"])
                for row in alias_rows
                if row.get("class") == document.class_name
                and row.get("ontology_property") == property_name
                and isinstance(row.get("amharic"), str)
            ]
            english_aliases = [
                str(alias)
                for row in alias_rows
                if row.get("class") == document.class_name
                and row.get("ontology_property") == property_name
                and isinstance(row.get("english_aliases"), list)
                for alias in row["english_aliases"]
                if isinstance(alias, str)
            ]
            amharic_aliases = _dedupe(_split_aliases(fields["amharic aliases"]) + row_aliases)
            text = (
                f"Class: {document.class_name} | Property: {property_name} | "
                f"Type: {fields['xsd type']} | Description: {fields['description']}"
            )
            payload: dict[str, Any] = {
                "class": document.class_name,
                "property": property_name,
                "xsd_type": fields["xsd type"],
                "description": fields["description"],
                "amharic_aliases": amharic_aliases,
                "english_aliases": _dedupe(english_aliases),
                "source_url": fields["source_url"],
                "text": text,
            }
            chunks.append(
                OntologyChunk(
                    chunk_id=_chunk_id(document.class_name, property_name),
                    text=text,
                    payload=payload,
                )
            )

    return chunks


def qdrant_client_from_settings(settings: Settings | None = None) -> Any:
    from qdrant_client import QdrantClient

    resolved = settings or Settings()
    return QdrantClient(url=resolved.qdrant_url, api_key=resolved.qdrant_api_key)


def create_collection(
    client: Any,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    *,
    dense_vector_size: int = DEFAULT_DENSE_VECTOR_SIZE,
    recreate: bool = False,
) -> None:
    """Create the named-vector Qdrant collection and class payload index."""

    from qdrant_client import models

    if recreate and client.collection_exists(collection_name):
        client.delete_collection(collection_name=collection_name)

    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config={
                DENSE_VECTOR_NAME: models.VectorParams(
                    size=dense_vector_size,
                    distance=models.Distance.COSINE,
                )
            },
            sparse_vectors_config={SPARSE_VECTOR_NAME: models.SparseVectorParams()},
        )

    try:
        client.create_payload_index(
            collection_name=collection_name,
            field_name="class",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
    except Exception as exc:  # pragma: no cover - client error type differs by transport.
        message = str(exc).lower()
        if "already exists" not in message and "conflict" not in message:
            raise


def build_points(
    chunks: Iterable[OntologyChunk],
    *,
    dense_embedder: DenseEmbedder = embed_dense,
    sparse_embedder: SparseEmbedder = embed_sparse,
) -> list[Any]:
    from qdrant_client import models

    points = []
    for chunk in chunks:
        points.append(
            models.PointStruct(
                id=chunk.chunk_id,
                vector={
                    DENSE_VECTOR_NAME: dense_embedder(chunk.embedding_text),
                    SPARSE_VECTOR_NAME: qdrant_sparse_vector(sparse_embedder(chunk.embedding_text)),
                },
                payload=chunk.payload,
            )
        )
    return points


def upsert_chunks(
    client: Any,
    chunks: Iterable[OntologyChunk],
    collection_name: str = DEFAULT_COLLECTION_NAME,
    *,
    dense_embedder: DenseEmbedder = embed_dense,
    sparse_embedder: SparseEmbedder = embed_sparse,
) -> None:
    """Upsert chunks into Qdrant with stable IDs."""

    points = build_points(chunks, dense_embedder=dense_embedder, sparse_embedder=sparse_embedder)
    if points:
        client.upsert(collection_name=collection_name, points=points, wait=True)


def index_corpus(
    *,
    data_dir: Path | str = "data",
    collection_name: str = DEFAULT_COLLECTION_NAME,
    rebuild: bool = False,
    dense_vector_size: int = DEFAULT_DENSE_VECTOR_SIZE,
    dense_embedder: DenseEmbedder = embed_dense,
    sparse_embedder: SparseEmbedder = embed_sparse,
    client: Any | None = None,
) -> int:
    resolved_client = client or qdrant_client_from_settings()
    chunks = chunk_corpus(data_dir)
    create_collection(
        resolved_client,
        collection_name,
        dense_vector_size=dense_vector_size,
        recreate=rebuild,
    )
    upsert_chunks(
        resolved_client,
        chunks,
        collection_name,
        dense_embedder=dense_embedder,
        sparse_embedder=sparse_embedder,
    )
    return len(chunks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args(argv)

    count = index_corpus(
        data_dir=args.data_dir, collection_name=args.collection, rebuild=args.rebuild
    )
    print(f"Indexed {count} ontology property chunks into {args.collection}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
