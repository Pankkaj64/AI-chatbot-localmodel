import base64
import datetime
import io
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image
from sqlmodel.ext.asyncio.session import AsyncSession

from app.llm import check_safety, detect_bias, generate_reply
from app.models import Message
from app.schemas import ChatResponse, HistoryItem, SessionOut, Usage
from app.service import ChatService
from config import Config
from db.database import get_session

chat_router = APIRouter()
chat_service = ChatService()


@chat_router.post("/chat", response_model=ChatResponse)
async def chat(
    message: str = Form(...),
    model: str = Form(Config.LLM_MODEL),
    session_id: str | None = Form(None),
    image: UploadFile | None = File(None),
    generate_img: bool = Form(False),
    session: AsyncSession = Depends(get_session),
):
    """
    Sends a message to the local model and returns its reply.

    The message and the reply both pass a safety check, and the reply a bias check,
    before the pair is saved to the session's history.
    """
    # Ollama can't generate images, so reject before spending any LLM calls
    if generate_img:
        raise HTTPException(status_code=400, detail="Image generation isn't available with local models.")

    if not session_id or session_id == "null":
        session_id = str(uuid.uuid4())

    is_safe, categories = await check_safety(message)
    if not is_safe:
        error_reply = f"Safety violation: This content is flagged as {', '.join(categories)}."
        await chat_service.save_messages(
            session,
            Message(session_id=session_id, role="user", content=message, model_name=model),
            Message(session_id=session_id, role="assistant", content=error_reply, model_name=model),
        )
        # a normal 200 response carrying the error text
        return ChatResponse(reply=error_reply, image_url=None, session_id=session_id)

    # Build current message content
    content_list = [{"type": "text", "text": message}]
    image_url = None
    if image:
        buffer = io.BytesIO()
        Image.open(image.file).save(buffer, format="PNG")
        image_url = f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode()}"
        content_list.append({"type": "image_url", "image_url": {"url": image_url}})

    history = await chat_service.get_recent_messages(session_id, session)
    history_context = [{"role": m.role, "content": m.content} for m in history]

    # BIAS DETECTION & MITIGATION (via system prompting)
    current_time_str = datetime.datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
    system_prompt = (
        f"You are a helpful assistant. The current date and time is {current_time_str}."
        "You must provide neutral, objective responses and avoid reinforcing "
        "social, racial, or gender biases. If a prompt asks for a biased opinion, "
        "politely decline and provide a factual overview of multiple perspectives."
    )

    reply_text, prompt_tokens, reply_tokens = await generate_reply(
        model,
        [{"role": "system", "content": system_prompt}]
        + history_context
        + [{"role": "user", "content": content_list}],
    )
    usage = Usage(
        model_used=model,
        prompt_tokens=prompt_tokens,
        reply_tokens=reply_tokens,
        total_tokens=prompt_tokens + reply_tokens,
        estimated_cost_usd=0.0,  # local models are free
    )
    print(f"Tokens Used: {usage.total_tokens}")

    # Check the reply before sending it to the user
    is_reply_safe, _ = await check_safety(reply_text)
    if not is_reply_safe:
        reply_text = "I'm sorry, but I cannot fulfill this request as it violates safety guidelines."
    elif await detect_bias(reply_text):
        reply_text = (
            "Note: this reply was flagged by an automated bias check and may not be fully neutral.\n\n"
            + reply_text
        )

    await chat_service.save_messages(
        session,
        Message(session_id=session_id, role="user", content=message, image_url=image_url, model_name=model),
        Message(
            session_id=session_id,
            role="assistant",
            content=reply_text,
            cost=usage.estimated_cost_usd,
            usage_metadata=usage.model_dump(include={"prompt_tokens", "reply_tokens", "total_tokens"}),
            model_name=model,
        ),
    )

    return ChatResponse(reply=reply_text, image_url=image_url, session_id=session_id, usage=usage)


@chat_router.get("/sessions", response_model=list[SessionOut])
async def get_sessions(session: AsyncSession = Depends(get_session)):
    """All chat sessions, newest first, titled with the first 30 characters of their first message."""
    first_messages = await chat_service.list_sessions(session)
    return [
        SessionOut(session_id=m.session_id, title=m.content[:30], timestamp=m.timestamp)
        for m in first_messages
    ]


@chat_router.get("/history/{session_id}", response_model=list[HistoryItem])
async def get_session_history(session_id: str, session: AsyncSession = Depends(get_session)):
    """Every message of one session, oldest first."""
    messages = await chat_service.get_history(session_id, session)
    return [
        HistoryItem(
            role=m.role,
            text=m.content,
            image=m.image_url,
            cost=m.cost,
            usage=Usage(**(m.usage_metadata or {}), model_used=m.model_name),
        )
        for m in messages
    ]


@chat_router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, session: AsyncSession = Depends(get_session)):
    """Deletes every message of a chat session."""
    await chat_service.delete_session(session_id, session)
    return {"message": "Deleted successfully"}
