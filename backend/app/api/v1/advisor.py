from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.ai.observability import ai_user_scope
from app.db.session import get_db
from app.crud import advisor as advisor_crud
from app.schemas.advisor import AdvisorChatRequest, AdvisorChatResponse, AdvisorHistoryMessage
from app.services.advisor_service import answer_advisor
from app.api.v1.ai_quota import reserve_ai_generation

router = APIRouter()


@router.get("/history", response_model=list[AdvisorHistoryMessage])
def history(db: Session = Depends(get_db)):
    return advisor_crud.list_recent(db, int(db.info.get("current_user_id") or 0))


@router.delete("/history", status_code=204)
def clear_history(db: Session = Depends(get_db)):
    advisor_crud.clear(db, int(db.info.get("current_user_id") or 0))
    return Response(status_code=204)


@router.post("/chat", response_model=AdvisorChatResponse)
def chat(payload: AdvisorChatRequest, db: Session = Depends(get_db)):
    user_id = int(db.info.get("current_user_id") or 0)
    reserve_ai_generation(db)
    # Conversation context comes from durable, user-scoped history, never from
    # untrusted client state. Retain only a short context for prompt limits.
    history = [
        {"role": item.role, "content": item.content}
        for item in advisor_crud.list_recent(db, user_id, limit=8)
    ]
    advisor_crud.append(db, user_id, "user", payload.message.strip())
    with ai_user_scope(user_id):
        reply = answer_advisor(
            db,
            user_id,
            payload.message,
            history,
            payload.language,
            payload.active_page,
            payload.active_job_id,
        )
    advisor_crud.append(
        db,
        user_id,
        "assistant",
        reply["answer"],
        sources=reply["sources"],
        suggested_prompts=reply["suggested_prompts"],
        used_fallback=reply["used_fallback"],
    )
    return reply
