import base64
import datetime
import io
import uuid
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Message
from app.schemas import ChatResponse, HistoryItem, SessionOut, Usage
from app.service import ChatService
from config import Config
from db.database import get_session
from app.agent import run_agent_reply
from app.llm import check_safety, detect_bias
from app.project_memory import get_recent_project_notes
from app.agent_registry import get_tool_definitions

chat_router = APIRouter()
chat_service = ChatService()


VISION_MODELS = {
    "gemma3",
    "gemma3:latest",
    "qwen2.5vl:3b",
    "qwen3-vl:2b",
}

@chat_router.post("/chat", response_model=ChatResponse)
async def chat(
    message: str = Form(...),
    model: str = Form(Config.LLM_MODEL),
    session_id: str | None = Form(None),
    images: list[UploadFile] | None = File(None),
    generate_img: bool = Form(False),
    session: AsyncSession = Depends(get_session),
    project_name: str | None = Form(None),
):
    """
    Sends a message to the local model and returns its reply.

    The message and the reply both pass a safety check, and the reply a bias check,
    before the pair is saved to the session's history.
    """
    fallback_project = (
        Config.DEFAULT_PROJECT
        if Config.DEFAULT_PROJECT in Config.PROJECTS
        else next(iter(Config.PROJECTS), "")
    )
    project_name = (project_name or fallback_project or "").strip() or None
    if project_name and project_name not in Config.PROJECTS:
        raise HTTPException(status_code=400, detail="Selected project is not configured.")

    request_tools = get_tool_definitions(bool(project_name), message)
    tool_names = {item["function"]["name"] for item in request_tools}
    project_tool_names = {
        "list_project_files", "read_project_file", "search_project_files",
        "search_project_knowledge", "remember_project_note",
    }
    project_tools_enabled = bool(tool_names & project_tool_names)
    project_notes = (
        await get_recent_project_notes(project_name)
        if project_name and project_tools_enabled
        else []
    )
    notes_text = "\n".join(f"- {note}" for note in project_notes)

    # Ollama can't generate images, so reject before spending any LLM calls
    if generate_img:
        raise HTTPException(status_code=400, detail="Image generation isn't available with local models.")

    if images and model not in VISION_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"{model} does not support images. Select a vision model"
        )
        
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
    image_urls = []
    for upload in images or []:
        try:
            buffer = io.BytesIO()

            with Image.open(upload.file) as uploaded_image:
                uploaded_image.load()
                uploaded_image.convert("RGB").save(buffer, format="PNG")

        except (OSError, Image.DecompressionBombError):
            raise HTTPException(
                status_code=400,
                detail=f"{upload.filename or 'An uploaded file'} is not a valid image.",
            )

        image_url = (
            "data:image/png;base64,"
            + base64.b64encode(buffer.getvalue()).decode("ascii")
        )
        image_urls.append(image_url)
        content_list.append(
            {
                "type": "image_url",
                "image_url": {"url": image_url},
            }
        )

    history = await chat_service.get_recent_messages(session_id, session)
    history_context = [{"role": m.role, "content": m.content} for m in history]

    # BIAS DETECTION & MITIGATION (via system prompting)
    current_time_str = datetime.datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")

    if project_tools_enabled:
        system_prompt = (
            f"You are a helpful assistant for project '{project_name}'. "
            f"Current date and time: {current_time_str}. "
            "Use project file or RAG tools when they help answer project questions. "
            "Cite evidence with relative file paths and line numbers when available. "
            "You may inspect files but cannot edit them or run commands. Suggest code "
            "changes for the user to apply. Save project notes only when explicitly "
            "asked. Never invent file contents or claim you changed files. "
            "Answer directly and do not output internal reasoning."
        )
    elif "search_arxiv" in tool_names:
        system_prompt = (
            "You are a helpful assistant. Use the arXiv tool to find papers when "
            "relevant, identify them as arXiv sources, and answer directly. "
            "Do not output internal reasoning."
        )
    else:
        # Keep ordinary turns short so small local reasoning models can finish.
        system_prompt = (
            "You are a helpful assistant. Answer the user's request directly. "
            "Be concise unless the user asks for detail. Do not output analysis, "
            "a thinking section, or internal reasoning."
        )

    if notes_text:
        system_prompt += f"\n\nSaved notes for this project:\n{notes_text}"

    reply_text, prompt_tokens, reply_tokens = await run_agent_reply(
        model,
        [{"role": "system", "content": system_prompt}]
        + history_context
        + [{"role": "user", "content": content_list}],
        project_name=project_name,
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
        Message(session_id=session_id, role="user", content=message, image_url=json.dumps(image_urls) if image_urls else None, model_name=model),
        Message(
        session_id=session_id,
        role="assistant",
        content=reply_text,
        cost=usage.estimated_cost_usd,
        usage_metadata=usage.model_dump(
            include={"prompt_tokens", "reply_tokens", "total_tokens"}
        ),
        model_name=model,
    ),
    )

    return ChatResponse(
        reply=reply_text, 
        image_url=image_urls[0] if image_urls else None,
        image_urls=image_urls,
        session_id=session_id,
        usage=usage,
        )


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
    messages = await chat_service.get_history(session_id, session)
    result = []

    for m in messages:
        image_urls = decode_image_urls(m.image_url)
        result.append(
            HistoryItem(
                role=m.role,
                text=m.content,
                image=image_urls[0] if image_urls else None,
                images=image_urls,
                cost=m.cost,
                usage=Usage(**(m.usage_metadata or {}), model_used=m.model_name),
            )
        )

    return result

@chat_router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, session: AsyncSession = Depends(get_session)):
    """Deletes every message of a chat session."""
    await chat_service.delete_session(session_id, session)
    return {"message": "Deleted successfully"}



def decode_image_urls(value: str | None) -> list[str]:
    if not value:
        return []

    try:
        decoded = json.loads(value)
        if isinstance(decoded, list):
            return decoded
    except json.JSONDecodeError:
        pass

    # Existing database rows stored one plain data URL.
    return [value]
