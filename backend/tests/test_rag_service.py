"""Tests for the ApplyEase RAG layer (retrieval over the user's own data).

The RAG entry point is `app.services.rag_service.retrieve_context`, used by the
real AI call sites (material generation) to ground prompts in the applicant's
experiences/documents. These tests run entirely offline: Milvus is unreachable
in CI, so the service falls back to the deterministic local embedding path, which
is exactly the logic under test.
"""

import sys
from types import SimpleNamespace

import pytest

from app.ai.material_generator import _build_rag_context
from app.db.session import Base, SessionLocal
from app.models.document import Document
from app.models.experience import Experience
from app.services import rag_service
from app.services.rag_service import format_context, retrieve_context, retrieve_user_context


@pytest.fixture(autouse=True)
def _create_tables():
    # The test sqlite engine (StaticPool, set by conftest) is shared process-wide
    # across test files, so we only create tables (idempotent) and keep seeds
    # isolated by unique user_id / primary-key ranges. We never drop_all, which
    # would wipe tables other test files rely on.
    Base.metadata.create_all(SessionLocal().bind)
    yield


def _seed_user(db, user_id: int):
    # Idempotent: clear any prior seed for this user before re-inserting, so the
    # shared (non-dropped) test database can be seeded repeatedly without
    # UNIQUE/primary-key collisions across tests. Primary keys are derived from
    # user_id so different users never collide on the same fixed id.
    db.query(Document).filter(Document.user_id == user_id).delete()
    db.query(Experience).filter(Experience.user_id == user_id).delete()
    db.commit()

    e1, e2, e3, d1 = user_id * 10 + 1, user_id * 10 + 2, user_id * 10 + 3, user_id * 10 + 9

    db.add(
        Experience(
            id=e1,
            user_id=user_id,
            title="Kubernetes Platform Engineer",
            organization="Acme Cloud",
            confirmed=True,
            description="Operated a Kubernetes platform and reduced incident MTTR by 40%.",
            skills=["Kubernetes", "Go"],
            achievements=[],
        )
    )
    db.add(
        Experience(
            id=e2,
            user_id=user_id,
            title="Biology Research Assistant",
            organization="HKU",
            confirmed=True,
            description="Ran PCR assays and analyzed sequencing data in Python.",
            skills=["Biology", "Python"],
            achievements=[],
        )
    )
    db.add(
        Document(
            id=d1,
            user_id=user_id,
            filename="cv.pdf",
            sha256="seed-cv-pdf",
            content_type="application/pdf",
        )
    )
    db.add(
        Experience(
            id=e3,
            user_id=user_id,
            title="Data Engineer",
            organization="Acme Cloud",
            confirmed=True,
            description="Built Kafka pipelines for real-time analytics.",
            skills=["Kafka", "Python"],
            achievements=[],
            document_id=d1,
        )
    )
    db.commit()


def test_retrieve_context_ranks_relevant_experience_first():
    with SessionLocal() as db:
        _seed_user(db, user_id=5001)

        results = retrieve_context(db, 5001, "Kubernetes platform operations", limit=4)

        assert results, "expected at least one retrieved passage"
        labels = [label for label, _text, _score in results]
        # The Kubernetes experience must be the top hit for a Kubernetes query.
        assert "Kubernetes" in labels[0]


def test_retrieve_context_scoped_to_requesting_user():
    with SessionLocal() as db:
        _seed_user(db, user_id=5002)
        # A different user with no data must get nothing back.
        results = retrieve_context(db, 9999, "Kubernetes platform operations")
        assert results == []


def test_retrieve_context_empty_when_user_has_no_data():
    with SessionLocal() as db:
        assert retrieve_context(db, 7777, "anything") == []


def test_retrieval_excludes_unconfirmed_experience_drafts():
    with SessionLocal() as db:
        _seed_user(db, user_id=5006)
        db.add(
            Experience(
                id=50069,
                user_id=5006,
                title="Unconfirmed confidential draft",
                organization="Draft only",
                confirmed=False,
                description="Do not use this in any application material.",
                skills=["SecretSkill"],
                achievements=[],
            )
        )
        db.commit()

        results = retrieve_context(db, 5006, "confidential draft SecretSkill", limit=10)

        rendered = format_context(results)
        assert "Unconfirmed confidential draft" not in rendered
        assert "SecretSkill" not in rendered


def test_format_context_renders_labels_and_text():
    ctx = format_context([("Experience: X", "Did Y.", 0.9)])
    assert "Experience: X" in ctx
    assert "Did Y." in ctx

    assert format_context([]) == ""


def test_milvus_label_is_utf8_safe_and_within_schema_limit():
    original = "香港大學資料科學專案" * 80
    shortened = rag_service._milvus_label(original)

    assert len(shortened.encode("utf-8")) <= 256
    assert shortened
    assert original.startswith(shortened)


def test_retrieve_user_context_is_deterministic_and_capped():
    with SessionLocal() as db:
        _seed_user(db, user_id=5003)
        a = retrieve_user_context(db, 5003, "Kubernetes", limit=2)
        b = retrieve_user_context(db, 5003, "Kubernetes", limit=2)
        assert a == b
        assert len(a) <= 2
        assert all(score <= 1.0 for _label, _text, score in a)


def test_retrieve_context_hits_document_sourced_experience():
    with SessionLocal() as db:
        _seed_user(db, user_id=5005)
        results = retrieve_context(db, 5005, "Kafka real-time analytics pipelines", limit=4)
        assert results, "expected a hit from the document-sourced experience"
        assert any("Kafka" in text for _label, text, _score in results)


def test_build_rag_context_returns_none_without_db():
    # When no db/user_id is supplied the generator must degrade gracefully.
    assert _build_rag_context(None, None, "query") is None
    assert _build_rag_context("db", None, "query") is None


def test_build_rag_context_injects_user_passages():
    with SessionLocal() as db:
        _seed_user(db, user_id=5004)
        context = _build_rag_context(db, 5004, "Kubernetes platform")
        assert context is not None
        assert "Kubernetes" in context


def test_milvus_index_is_tenant_scoped_and_refreshes_stale_passages(monkeypatch):
    """ANN calls must never search/delete IDs belonging to a different user."""

    class FakeSchema:
        def add_field(self, *_args, **_kwargs):
            pass

    class FakeIndexParams:
        def add_index(self, *_args, **_kwargs):
            pass

    class FakeMilvusClient:
        latest = None

        def __init__(self, **_kwargs):
            self.query_filter = None
            self.search_filter = None
            self.deleted = []
            self.records = []
            FakeMilvusClient.latest = self

        def has_collection(self, _collection):
            return False

        def create_schema(self, **_kwargs):
            return FakeSchema()

        def prepare_index_params(self):
            return FakeIndexParams()

        def create_collection(self, *_args, **_kwargs):
            pass

        def create_index(self, *_args, **_kwargs):
            pass

        def load_collection(self, *_args, **_kwargs):
            pass

        def query(self, _collection, *, filter, **_kwargs):
            self.query_filter = filter
            # Represents only a stale record already owned by this tenant.
            return [{"id": 42}]

        def delete(self, _collection, *, ids):
            self.deleted = ids

        def upsert(self, _collection, records):
            self.records = records

        def flush(self, *_args, **_kwargs):
            pass

        def search(self, _collection, *, filter, **_kwargs):
            self.search_filter = filter
            return [[{"id": self.records[0]["id"], "distance": 0.9}]]

    fake_module = SimpleNamespace(
        DataType=SimpleNamespace(INT64="INT64", VARCHAR="VARCHAR", FLOAT_VECTOR="FLOAT_VECTOR"),
        MilvusClient=FakeMilvusClient,
    )
    monkeypatch.setitem(sys.modules, "pymilvus", fake_module)
    monkeypatch.setattr(rag_service, "ollama_embed", lambda _text: [0.25, 0.75])

    with SessionLocal() as db:
        _seed_user(db, user_id=5010)
        result = rag_service._milvus_search(db, 5010, "Kubernetes", limit=2)

    client = FakeMilvusClient.latest
    assert result and "Kubernetes" in result[0][0]
    assert client.query_filter == "user_id == 5010"
    assert client.search_filter == "user_id == 5010"
    assert client.deleted == [42]
    assert client.records and all(record["user_id"] == 5010 for record in client.records)
    assert rag_service._passage_id(5010, "same", "text") != rag_service._passage_id(
        5011, "same", "text"
    )
