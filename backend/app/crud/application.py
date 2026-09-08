from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import Application, ApplicationQuestion


def get(db: Session, application_id: int):

    return db.get(Application, application_id)


def get_question(db: Session, application_id: int, question_id: int):

    return db.scalar(
        select(ApplicationQuestion).where(
            ApplicationQuestion.id == question_id,
            ApplicationQuestion.application_id == application_id,
        )
    )


def list_questions(db: Session, application_id: int):

    return db.scalars(
        select(ApplicationQuestion)
        .where(ApplicationQuestion.application_id == application_id)
        .order_by(ApplicationQuestion.id)
    ).all()


def list_by_job(db: Session, job_id: int):
    return db.scalars(
        select(Application)
        .where(Application.job_id == job_id)
        .order_by(Application.created_at.desc(), Application.id.desc())
    ).all()


def latest_by_job(db: Session, job_id: int) -> Application | None:
    return db.scalar(
        select(Application)
        .where(Application.job_id == job_id)
        .order_by(Application.created_at.desc(), Application.id.desc())
        .limit(1)
    )


def create_with_questions(db: Session, job_id: int, raw_text: str, questions: list[dict]):
    application = Application(job_id=job_id, raw_text=raw_text)

    db.add(application)

    db.flush()

    records = [ApplicationQuestion(application_id=application.id, **values) for values in questions]

    db.add_all(records)

    db.commit()

    db.refresh(application)

    for record in records:
        db.refresh(record)

    return application, records


def create_question(
    db: Session,
    application_id: int,
    question: str = "",
    *,
    question_type: str = "general",
    max_characters: int = 300,
    required: bool = True,
):
    record = ApplicationQuestion(
        application_id=application_id,
        question=question.strip(),
        question_type=question_type,
        max_characters=max_characters,
        required=required,
        answer={},
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update_question(db: Session, question: ApplicationQuestion, values: dict):
    for key, value in values.items():
        setattr(question, key, value)
    db.commit()
    db.refresh(question)
    return question


def save_answer(db: Session, question: ApplicationQuestion, answer: dict):
    question.answer = answer

    db.commit()

    db.refresh(question)

    return question
