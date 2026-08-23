from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings

is_sqlite = settings.database_url.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}
pool_kwargs = (
    {"poolclass": StaticPool}
    if settings.database_url in {"sqlite://", "sqlite:///:memory:"}
    else {}
)
engine = create_engine(
    settings.database_url, connect_args=connect_args, pool_pre_ping=True, **pool_kwargs
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()

    try:

        yield db

    finally:
        db.close()


# Ownership is enforced at the session boundary so every existing API route and
# CRUD query receives the same isolation rule. The auth dependency sets this
# value before business code runs; new records inherit it automatically.
@event.listens_for(SessionLocal.class_, "before_flush")
def assign_owner(session, flush_context, instances):
    owner_id = session.info.get("current_user_id")

    if owner_id is None:

        return

    for obj in session.new:

        if hasattr(obj, "user_id") and getattr(obj, "user_id", None) is None:
            obj.user_id = owner_id


@event.listens_for(SessionLocal.class_, "do_orm_execute")
def enforce_owner(execute_state):
    owner_id = execute_state.session.info.get("current_user_id")

    if owner_id is None or not execute_state.is_select:

        return
    from app.models.application import Application, ApplicationQuestion

    from app.models.document import Document

    from app.models.experience import Experience

    from app.models.job import Job

    from app.models.material import GeneratedMaterial

    from app.models.resource import ResourceFeedback, ResourceProgress
    from app.models.research_plan import ResearchPlan

    from app.models.tracker import TrackedApplication

    from app.models.ai_observation import AIInvocation
    from app.models.advisor import AdvisorConversationMessage
    from app.models.opportunity import OpportunitySearch
    from app.models.starter_plan import StarterLearningPlan

    owned = (
        Application,
        ApplicationQuestion,
        Document,
        Experience,
        Job,
        GeneratedMaterial,
        ResourceProgress,
        ResourceFeedback,
        TrackedApplication,
        AIInvocation,
        ResearchPlan,
        AdvisorConversationMessage,
        OpportunitySearch,
        StarterLearningPlan,
    )

    for model in owned:
        execute_state.statement = execute_state.statement.options(
            __import__("sqlalchemy.orm", fromlist=["with_loader_criteria"]).with_loader_criteria(
                model, lambda cls: cls.user_id == owner_id, include_aliases=True
            )
        )
