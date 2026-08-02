"""API FastAPI — endpoints chat, feedback, produits, santé."""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agent.agent import SalesAgent
from app.api.whatsapp_webhook import router as whatsapp_router
from app.api.twilio_webhook import router as twilio_router
from app.database.models import Conversation, Product, UserFeedback
from app.database.session import get_db, init_db
from app.schemas import ChatRequest, ChatResponse, FeedbackRequest
from app.api.whapi_webhook import router as whapi_router


app = FastAPI(title="Assistant Commercial WhatsApp", version="1.0.0")
app.include_router(whatsapp_router)
app.include_router(twilio_router)
app.include_router(whapi_router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    db.add(Conversation(session_id=request.session_id, customer_phone=request.customer_phone,
                         role="user", content=request.message))
    db.commit()

    agent = SalesAgent(db)
    result = agent.handle_message(request.session_id, request.customer_phone, request.message)

    db.add(Conversation(session_id=request.session_id, customer_phone=request.customer_phone,
                         role="assistant", content=result["response"]))
    db.commit()

    return ChatResponse(
        session_id=request.session_id,
        response=result["response"],
        retrieval_method=result["retrieval_method"],
        tools_called=result["tools_called"],
        latency_ms=result["latency_ms"],
        interaction_log_id=result["interaction_log_id"],
    )


@app.post("/feedback")
def feedback(request: FeedbackRequest, db: Session = Depends(get_db)):
    db.add(UserFeedback(
        interaction_log_id=request.interaction_log_id,
        session_id=request.session_id,
        rating=request.rating,
        comment=request.comment,
    ))
    db.commit()
    return {"status": "recorded"}


@app.get("/products/count")
def products_count(db: Session = Depends(get_db)):
    return {"count": db.query(func.count(Product.id)).scalar()}


@app.get("/conversations/{session_id}")
def conversation_history(session_id: str, db: Session = Depends(get_db)):
    rows = (
        db.query(Conversation)
        .filter(Conversation.session_id == session_id)
        .order_by(Conversation.created_at)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Session inconnue")
    return [{"role": r.role, "content": r.content, "created_at": r.created_at.isoformat()} for r in rows]
