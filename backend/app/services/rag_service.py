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
from collections import Counter
import httpx

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Experience, Document
from app.config import settings

DIMENSIONS = 256

# Small, citation-friendly evidence units.  60 characters is approximately
# fifteen percent overlap at the 400-character upper bound.
CHUNK_MIN_CHARS = 200
CHUNK_MAX_CHARS = 400
CHUNK_OVERLAP = 60
VECTOR_CANDIDATE_K = 20
DEFAULT_RESULT_K = 5

# Changing the collection layout is a security boundary: v2 explicitly stores
# a tenant field and scopes every ANN query to it. A versioned/model-derived
# name avoids accidentally querying an old, unpartitioned collection after an
# upgrade or embedding-model change.
COLLECTION_SCHEMA_VERSION = "v3"

# Content-addressed cache for offline/local retrieval.  An edited passage gets
# a new key, while unchanged evidence is embedded only once per process.
_LOCAL_EMBED_CACHE: dict[int, tuple[str, list[float]]] = {}


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
    # Keep Latin words intact, while splitting CJK text into overlapping
    # character n-grams. Python's ``\w+`` treats a whole Chinese sentence as
    # one token, making semantically related Chinese web snippets look
    # unrelated to the query. This remains a deterministic fallback, not a
    # brittle exact-string matcher.
    normalized = text.casefold()
    tokens = re.findall(r"[a-z0-9+#.-]+|[\u4e00-\u9fff]", normalized)
    cjk = re.findall(r"[\u4e00-\u9fff]", normalized)
    tokens.extend("".join(cjk[index : index + 2]) for index in range(max(0, len(cjk) - 1)))
    for token in tokens:
        index = int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % DIMENSIONS
        vector[index] += 1.0
    length = math.sqrt(sum(value * value for value in vector))
    return [value / length for value in vector] if length else vector


def _cached_embed(label: str, text: str) -> list[float]:
    key = _passage_id(0, label, text)
    cached = _LOCAL_EMBED_CACHE.get(key)
    if cached and cached[0] == text:
        return cached[1]
    vector = embed(text)
    _LOCAL_EMBED_CACHE[key] = (text, vector)
    return vector


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def _lexical_tokens(text: str) -> list[str]:
    """Tokenise Latin words and CJK unigrams/bigrams for BM25 matching."""
    normalized = (text or "").casefold()
    words = re.findall(r"[a-z0-9+#.-]+", normalized)
    cjk = re.findall(r"[\u4e00-\u9fff]", normalized)
    return words + cjk + ["".join(cjk[i : i + 2]) for i in range(max(0, len(cjk) - 1))]


def _bm25_scores(query: str, passages: list[tuple[str, str]]) -> list[float]:
    """Return BM25 scores for exact company/skill/name matches."""
    query_terms = set(_lexical_tokens(query))
    docs = [_lexical_tokens(f"{label}\n{text}") for label, text in passages]
    if not query_terms or not docs:
        return [0.0] * len(docs)
    document_frequency = Counter(term for terms in docs for term in set(terms))
    average_length = sum(len(terms) for terms in docs) / max(len(docs), 1)
    scores: list[float] = []
    k1, b = 1.2, 0.75
    for terms in docs:
        counts = Counter(terms)
        length = len(terms)
        score = 0.0
        for term in query_terms:
            frequency = counts.get(term, 0)
            if not frequency:
                continue
            idf = math.log(1 + (len(docs) - document_frequency.get(term, 0) + 0.5) / (document_frequency.get(term, 0) + 0.5))
            score += idf * (frequency * (k1 + 1)) / (
                frequency + k1 * (1 - b + b * length / max(average_length, 1))
            )
        scores.append(score)
    return scores


def _hybrid_rerank(
    query: str,
    passages: list[tuple[str, str]],
    vector_scores: list[float],
    *,
    limit: int,
    candidate_k: int = VECTOR_CANDIDATE_K,
) -> list[tuple[str, str, float]]:
    """Fuse vector/BM25 top-K candidates, then deterministically rerank to K."""
    if not passages:
        return []
    lexical = _bm25_scores(query, passages)
    vector_order = sorted(range(len(passages)), key=lambda i: vector_scores[i], reverse=True)
    lexical_order = sorted(range(len(passages)), key=lambda i: lexical[i], reverse=True)
    candidate_ids = set(vector_order[:candidate_k]) | set(lexical_order[:candidate_k])
    max_lexical = max((lexical[i] for i in candidate_ids), default=0.0)
    ranked: list[tuple[float, int]] = []
    for index in candidate_ids:
        lexical_score = lexical[index] / max_lexical if max_lexical else 0.0
        # Semantic similarity carries most of the weight; lexical evidence
        # prevents company names and exact skills from being lost.
        score = 0.65 * max(0.0, vector_scores[index]) + 0.35 * lexical_score
        ranked.append((score, index))
    ranked.sort(key=lambda item: (item[0], vector_scores[item[1]], -item[1]), reverse=True)
    return [
        (passages[index][0], passages[index][1], round(score, 4))
        for score, index in ranked[: max(1, min(limit, len(ranked)))]
    ]


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
        # Prefer a sentence/paragraph boundary without ever exceeding the
        # configured maximum.  This keeps citations readable.
        boundary = max(
            text.rfind("\n", start + CHUNK_MIN_CHARS, end),
            text.rfind("。", start + CHUNK_MIN_CHARS, end),
            text.rfind(".", start + CHUNK_MIN_CHARS, end),
        )
        if boundary > start:
            end = boundary + 1
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
        heading = f"{exp.title or 'untitled'} @ {exp.organization or 'n/a'}"
        raw_parts = [
            str(exp.description or ""),
            *[
                str(item.get("text", ""))
                for item in (exp.achievements or [])
                if isinstance(item, dict) and item.get("text")
            ],
        ]
        bullets = [
            piece.strip()
            for part in raw_parts
            for piece in re.split(r"(?:\r?\n+|(?=^[•●▪‣*-]\s*))", part, flags=re.MULTILINE)
            if piece.strip()
        ]
        for bullet_index, bullet in enumerate(bullets, start=1):
            chunks = _chunk_text(bullet)
            for chunk_index, chunk in enumerate(chunks, start=1):
                suffix = f".{chunk_index}" if len(chunks) > 1 else ""
                label = f"Experience: {heading} · evidence {bullet_index}{suffix}"
                passages.append((label, chunk))
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


def index_user_context(db: Session, user_id: int) -> None:
    """Synchronise one user's evidence index after a write.

    CRUD callers invoke this after create/update/confirm/delete.  Failures are
    intentionally swallowed here: indexing is derived data and must never make
    a user's confirmed evidence write fail.  Retrieval still performs a safety
    reconciliation for edits made by older clients.
    """
    passages = _all_passages(db, user_id)
    for label, text in passages:
        _cached_embed(label, text)
    if settings.app_env == "test" or not passages:
        return
    try:
        from pymilvus import DataType, MilvusClient

        client = MilvusClient(uri=settings.milvus_uri)
        collection = _collection_name()
        if not client.has_collection(collection):
            dimension = len(ollama_embed(passages[0][1]))
            schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
            schema.add_field("id", DataType.INT64, is_primary=True)
            schema.add_field("user_id", DataType.INT64)
            bool_type = getattr(DataType, "BOOL", None)
            if bool_type is not None:
                schema.add_field("confirmed", bool_type)
            schema.add_field("label", DataType.VARCHAR, max_length=256)
            schema.add_field("vector", DataType.FLOAT_VECTOR, dim=dimension)
            client.create_collection(collection, schema=schema)
            index_params = client.prepare_index_params()
            index_params.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="COSINE")
            client.create_index(collection, index_params=index_params)
        client.load_collection(collection)
        tenant_filter = f"user_id == {int(user_id)}"
        known = {
            item["id"]
            for item in client.query(collection, filter=tenant_filter, output_fields=["id"], limit=16384)
        }
        records = []
        current_ids = set()
        for label, text in passages:
            passage_id = _passage_id(user_id, label, text)
            current_ids.add(passage_id)
            if passage_id in known:
                continue
            records.append(
                {
                    "id": passage_id,
                    "user_id": user_id,
                    "confirmed": True,
                    "label": _milvus_label(label),
                    "vector": ollama_embed(f"{label}\n{text}"),
                }
            )
        stale = known - current_ids
        if stale:
            client.delete(collection, ids=list(stale))
        if records:
            client.upsert(collection, records)
            client.flush(collection)
    except Exception:
        return


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
    if not client.has_collection(collection):
        # The dimension is only needed when the collection is first created.
        # Previously this call, plus one call for every passage below, ran on
        # every retrieval even though most user evidence had not changed.
        dimension = len(_cached_embed(f"{user_id}:schema", passages[0][1]))
        schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("id", DataType.INT64, is_primary=True)
        schema.add_field("user_id", DataType.INT64)
        bool_type = getattr(DataType, "BOOL", None)
        if bool_type is not None:
            schema.add_field("confirmed", bool_type)
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
    tenant_filter = f"user_id == {int(user_id)} and confirmed == true"
    existing = client.query(collection, filter=tenant_filter, output_fields=["id"], limit=16384)
    known = {item["id"] for item in existing}
    passage_by_id = {
        _passage_id(user_id, label, text): (label, text) for label, text in passages
    }
    candidate_records = [
        {
            "id": passage_id,
            "user_id": user_id,
            "confirmed": True,
            "label": _milvus_label(label),
        }
        for passage_id, (label, _text) in passage_by_id.items()
    ]
    current_ids = {record["id"] for record in candidate_records}
    stale_ids = known - current_ids
    if stale_ids:
        client.delete(collection, ids=list(stale_ids))
    # An edited passage gets a new content-derived ID, so only passages absent
    # from the tenant index need embedding and upsert. This makes steady-state
    # retrieval one query embedding instead of N evidence embeddings.
    new_records = [record for record in candidate_records if record["id"] not in known]
    if new_records:
        for record in new_records:
            label, text = passage_by_id[record["id"]]
            record["vector"] = ollama_embed(f"{label}\n{text}")
        # Upsert keeps a stable, current tenant index even when an experience
        # is edited; plain insert previously left stale vectors behind.
        client.upsert(collection, new_records)
        # Make the just-written evidence visible to the immediately following
        # search. Without this, first-use requests can observe an empty index
        # until Milvus performs its asynchronous flush.
        client.flush(collection)
    result = client.search(
        collection,
        data=[ollama_embed(query)],
        anns_field="vector",
        limit=max(VECTOR_CANDIDATE_K, limit * 4),
        filter=tenant_filter,
        output_fields=["label"],
    )[0]
    by_id = {_passage_id(user_id, label, text): (label, text) for label, text in passages}
    candidate_passages = []
    candidate_scores = []
    for hit in result:
        if hit["id"] in by_id:
            candidate_passages.append(by_id[hit["id"]])
            candidate_scores.append(float(hit["distance"]))
    return _hybrid_rerank(query, candidate_passages, candidate_scores, limit=limit)


def retrieve_user_context(
    db: Session, user_id: int, query: str, limit: int = DEFAULT_RESULT_K
) -> list[tuple[str, str, float]]:
    """Retrieve the most relevant fragments of a user's own data for a query.

    Returns a list of (label, text, score) triples, best first. Used by the real
    AI call sites to ground their prompts in the user's experiences/documents.
    """
    passages = _all_passages(db, user_id)
    if not passages:
        return []
    query_vector = _cached_embed("query:" + query, query)
    vector_scores = [
        _cosine(query_vector, _cached_embed(label, f"{label}\n{text}"))
        for label, text in passages
    ]
    return _hybrid_rerank(query, passages, vector_scores, limit=limit)


def retrieve_context(
    db: Session, user_id: int, query: str, limit: int = DEFAULT_RESULT_K
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
