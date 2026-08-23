"""Retrieval-Augmented Generation (RAG) for ApplyEase AI calls.

This service is the single place where ApplyEase augments its LLM prompts with
retrieved context. It is intentionally scoped to the *real* AI call sites in the
app (material generation, job analysis, application-form analysis, evaluation and
experience extraction): before those services call a model, they ask this service
for the most relevant fragments of the **user's own data** (work/education
experiences and uploaded documents) and inject them into the prompt.

The retrieval layer uses Ollama embeddings when available and a deterministic
local fallback (bag-of-words cosine) so the app stays usable in offline/test
environments. Milvus is used as the ANN index in production when reachable.

NOTE: this module is meant to be studied as the project's "AI agent learning"
material -- the RAG wiring here *is* the example of how an AI agent retrieves
grounding context before generating.
"""

from __future__ import annotations

import hashlib
import math
import re
import httpx

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Experience, Document
from app.config import settings

DIMENSIONS = 256

CHUNK_MAX_CHARS = 1200
CHUNK_OVERLAP = 200

# Changing the collection layout is a security boundary: v2 explicitly stores
# a tenant field and scopes every ANN query to it. A versioned/model-derived
# name avoids accidentally querying an old, unpartitioned collection after an
# upgrade or embedding-model change.
COLLECTION_SCHEMA_VERSION = "v2"


class RAGPurgeError(RuntimeError):
    """Raised when account deletion cannot remove its derived vector data."""


def ollama_embed(text: str) -> list[float]:
    """Use Ollama's embedding endpoint; caller falls back only in offline tests."""
    response = httpx.post(
        f"{settings.ollama_base_url.rstrip('/')}/api/embed",
        json={"model": settings.rag_embedding_model, "input": text},
        timeout=settings.llm_timeout_seconds,
    )
    response.raise_for_status()
    values = response.json().get("embeddings", [[]])[0]
    if not values:
        raise ValueError("empty embedding")
    return [float(value) for value in values]


def embed(text: str) -> list[float]:
    """Deterministic local embedding fallback; safe for offline development/tests."""
    vector = [0.0] * DIMENSIONS
    for token in re.findall(r"[\w-]+", text.casefold()):
        index = int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % DIMENSIONS
        vector[index] += 1.0
    length = math.sqrt(sum(value * value for value in vector))
    return [value / length for value in vector] if length else vector


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def _chunk_text(
    text: str, max_chars: int = CHUNK_MAX_CHARS, overlap: int = CHUNK_OVERLAP
) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _experience_passages(db: Session, user_id: int) -> list[tuple[str, str]]:
    """Return (label, text) passages built from a user's structured experiences."""
    passages: list[tuple[str, str]] = []
    # Retrieval feeds generation paths, so it must preserve the same evidence
    # contract as the rest of ApplyEase: unconfirmed CV extractions are drafts,
    # never application evidence.
    rows = db.scalars(
        select(Experience).where(
            Experience.user_id == user_id,
            Experience.confirmed.is_(True),
        )
    ).all()
    for exp in rows:
        parts = [exp.title or "", exp.organization or "", exp.description or ""]
        text = "\n".join(part for part in parts if part).strip()
        if not text:
            continue
        label = f"Experience: {exp.title or 'untitled'} @ {exp.organization or 'n/a'}"
        passages.append((label, text))
    return passages


def _document_passages(db: Session, user_id: int) -> list[tuple[str, str]]:
    """Return (label, text) passages sourced from a user's uploaded documents.

    Document rows store only metadata (filename/sha256); the actual text from a
    CV lives in the Experience rows extracted from it (Experience.document_id).
    So each document's passages are the aggregated experiences linked to it.
    """
    passages: list[tuple[str, str]] = []
    docs = db.scalars(select(Document).where(Document.user_id == user_id)).all()
    for doc in docs:
        linked = db.scalars(
            select(Experience).where(
                Experience.document_id == doc.id,
                Experience.user_id == user_id,
                Experience.confirmed.is_(True),
            )
        ).all()
        if not linked:
            continue
        chunks = _chunk_text(
            "\n\n".join(
                piece
                for exp in linked
                for piece in (exp.title, exp.organization, exp.description)
                if piece
            )
        )
        for idx, chunk in enumerate(chunks):
            passages.append((f"Document: {doc.filename} (part {idx + 1})", chunk))
    return passages


def _all_passages(db: Session, user_id: int) -> list[tuple[str, str]]:
    return _experience_passages(db, user_id) + _document_passages(db, user_id)


def _collection_name() -> str:
    model_hash = hashlib.sha256(settings.rag_embedding_model.encode("utf-8")).hexdigest()[:12]
    return f"applyease_user_context_{COLLECTION_SCHEMA_VERSION}_{model_hash}"


def _passage_id(user_id: int, label: str, text: str) -> int:
    """Return a deterministic, tenant-scoped positive INT64 primary key."""
    digest = hashlib.sha256(f"{user_id}\0{label}\0{text}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)


def _milvus_label(label: str, max_bytes: int = 256) -> str:
    """Fit a display label into Milvus VARCHAR byte limits without bad UTF-8."""
    encoded = label.encode("utf-8")
    if len(encoded) <= max_bytes:
        return label
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def purge_user_context(user_id: int) -> None:
    """Delete every derived Milvus vector belonging to an account.

    This is deliberately fail-closed for real environments. Account deletion
    must not report success while a separate data store can still retain the
    applicant's derived context. Test runs have no Milvus dependency and are
    exercised through endpoint-level mocks instead.
    """
    if settings.app_env == "test":
        return
    try:
        from pymilvus import MilvusClient

        client = MilvusClient(uri=settings.milvus_uri)
        collection = _collection_name()
        if not client.has_collection(collection):
            return
        client.load_collection(collection)
        client.delete(collection, filter=f"user_id == {int(user_id)}")
        client.flush(collection)
    except Exception as exc:
        raise RAGPurgeError("Unable to remove derived vector data") from exc


def _milvus_search(
    db: Session, user_id: int, query: str, limit: int
) -> list[tuple[str, str, float]]:
    from pymilvus import DataType, MilvusClient

    passages = _all_passages(db, user_id)
    if not passages:
        return []
    client = MilvusClient(uri=settings.milvus_uri)
    collection = _collection_name()
    dimension = len(ollama_embed(passages[0][1]))
    if not client.has_collection(collection):
        schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("id", DataType.INT64, is_primary=True)
        schema.add_field("user_id", DataType.INT64)
        schema.add_field("label", DataType.VARCHAR, max_length=256)
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=dimension)
        client.create_collection(collection, schema=schema)
        # pymilvus 2.5 uses an IndexParams object rather than the pre-2.5
        # positional field-name/dict signature.
        index_params = client.prepare_index_params()
        index_params.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="COSINE")
        client.create_index(collection, index_params=index_params)
    # Standalone Milvus does not implicitly load a newly-created collection.
    # Loading on every call is idempotent and makes first-use retrieval work.
    client.load_collection(collection)
    # Never query or delete another user's vectors. The scalar filter is as
    # important as the deterministic ID: it prevents accidental cross-tenant
    # retrieval if a caller or future schema change supplies overlapping IDs.
    tenant_filter = f"user_id == {int(user_id)}"
    existing = client.query(collection, filter=tenant_filter, output_fields=["id"], limit=16384)
    known = {item["id"] for item in existing}
    records = [
        {
            "id": _passage_id(user_id, label, text),
            "user_id": user_id,
            "label": _milvus_label(label),
            "vector": ollama_embed(text),
        }
        for label, text in passages
    ]
    current_ids = {record["id"] for record in records}
    stale_ids = known - current_ids
    if stale_ids:
        client.delete(collection, ids=list(stale_ids))
    # Upsert keeps a stable, current tenant index even when an experience is
    # edited; plain insert previously left stale vectors behind indefinitely.
    if records:
        client.upsert(collection, records)
        # Make the just-written evidence visible to the immediately following
        # search. Without this, first-use requests can observe an empty index
        # until Milvus performs its asynchronous flush.
        client.flush(collection)
    result = client.search(
        collection,
        data=[ollama_embed(query)],
        anns_field="vector",
        limit=limit,
        filter=tenant_filter,
        output_fields=["label"],
    )[0]
    by_id = {_passage_id(user_id, label, text): (label, text) for label, text in passages}
    return [
        (by_id[hit["id"]][0], by_id[hit["id"]][1], round(float(hit["distance"]), 4))
        for hit in result
        if hit["id"] in by_id
    ]


def retrieve_user_context(
    db: Session, user_id: int, query: str, limit: int = 4
) -> list[tuple[str, str, float]]:
    """Retrieve the most relevant fragments of a user's own data for a query.

    Returns a list of (label, text, score) triples, best first. Used by the real
    AI call sites to ground their prompts in the user's experiences/documents.
    """
    passages = _all_passages(db, user_id)
    if not passages:
        return []
    query_vector = embed(query)
    scored = []
    for label, text in passages:
        score = _cosine(query_vector, embed(text))
        scored.append((label, text, round(score, 4)))
    return sorted(scored, key=lambda triple: triple[2], reverse=True)[:limit]


def retrieve_context(
    db: Session, user_id: int, query: str, limit: int = 4
) -> list[tuple[str, str, float]]:
    """Public retrieval entry point with Milvus acceleration when available."""
    try:
        result = _milvus_search(db, user_id, query, limit)
        if result:
            return result
    except Exception:
        # Production prefers Milvus + Ollama; offline/tests use the local fallback.
        pass
    return retrieve_user_context(db, user_id, query, limit)


def format_context(passages: list[tuple[str, str, float]]) -> str:
    """Render retrieved passages into a prompt-ready context block."""
    if not passages:
        return ""
    blocks = []
    for label, text, _ in passages:
        blocks.append(f"### {label}\n{text}")
    return "\n\n".join(blocks)
