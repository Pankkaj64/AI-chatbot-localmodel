import re

from app.agent_registry import dispatch_tool, get_tool_definitions
from app.llm import client
from openai import BadRequestError


MAX_AGENT_STEPS = 5
MAX_TOOL_CALLS = 4


def add_usage(response, totals: dict) -> None:
    """Accumulate token usage across model and tool rounds."""
    if response.usage:
        totals["prompt_tokens"] += response.usage.prompt_tokens or 0
        totals["reply_tokens"] += response.usage.completion_tokens or 0


def _last_user_text(messages: list[dict]) -> str:
    """Extract plain text from the latest user message, including image turns."""
    for item in reversed(messages):
        if item.get("role") != "user":
            continue
        content = item.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            )
    return ""


async def _retry_for_direct_answer(model: str, messages: list[dict], totals: dict) -> str:
    """Retry when a local reasoning model returns thoughts but no answer text."""
    retry_messages = [dict(item) for item in messages]
    for item in retry_messages:
        if item.get("role") == "system":
            item["content"] = (
                str(item.get("content", ""))
                + "\nAnswer the user's request directly in a concise final response. "
                "Do not output analysis, a thinking section, or internal reasoning."
            )
            break
    response = await client.chat.completions.create(
        model=model,
        messages=retry_messages,
        temperature=0.2,
        max_tokens=512,
        extra_body={"think": False},
    )
    add_usage(response, totals)
    return (response.choices[0].message.content or "").strip()


async def run_agent_reply(
    model: str,
    messages: list[dict],
    project_name: str | None = None,
) -> tuple[str, int, int]:
    """Let the model choose tools, run them, and produce a final answer."""
    totals = {"prompt_tokens": 0, "reply_tokens": 0}
    tool_calls_used = 0
    tool_definitions = get_tool_definitions(bool(project_name), _last_user_text(messages))

    for _ in range(MAX_AGENT_STEPS):
        request_options = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 700,
            # Ollama accepts this for models that expose thinking controls.
            "extra_body": {"think": False},
        }
        if tool_definitions:
            request_options["tools"] = tool_definitions
            request_options["tool_choice"] = "auto"
        try:
            response = await client.chat.completions.create(**request_options)
        except BadRequestError:
            # Some local models or Ollama versions do not implement tool calls.
            # Keep chat usable by retrying once without tools for that request.
            if "tools" not in request_options:
                raise
            tool_definitions = []
            request_options.pop("tools", None)
            request_options.pop("tool_choice", None)
            response = await client.chat.completions.create(**request_options)
        add_usage(response, totals)

        assistant_message = response.choices[0].message
        tool_calls = assistant_message.tool_calls or []

        # No tool call means this is the final user-facing answer.
        if not tool_calls:
            reply = assistant_message.content or ""
            reply = re.sub(
                r"(?:\s*</?function>\s*)+",
                " ",
                reply,
                flags=re.IGNORECASE,
            ).strip()

            if not reply:
                reply = await _retry_for_direct_answer(model, messages, totals)
            if not reply:
                reply = (
                    "The selected model did not return a final answer. Try Gemma 3 "
                    "or Qwen2.5 3B, or check the local Ollama model service."
                )

            return reply, totals["prompt_tokens"], totals["reply_tokens"]

        # Keep the model's tool-call message in the conversation.
        messages.append(assistant_message.model_dump(exclude_none=True))

        for tool_call in tool_calls:
            if tool_calls_used >= MAX_TOOL_CALLS:
                result = "Tool-call limit reached for this request."
            else:
                result = await dispatch_tool(
                    project_name=project_name,
                    tool_name=tool_call.function.name,
                    raw_arguments=tool_call.function.arguments,
                )
                tool_calls_used += 1

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

        if tool_calls_used >= MAX_TOOL_CALLS:
            break

    # Final answer after the agent reaches its tool-call limit.
    final_response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.2,
        max_tokens=700,
        extra_body={"think": False},
    )
    add_usage(final_response, totals)

    reply = final_response.choices[0].message.content or ""
    reply = re.sub(r"</?function>", "", reply, flags=re.IGNORECASE).strip()

    if not reply:
        reply = await _retry_for_direct_answer(model, messages, totals)
    if not reply:
        reply = "The selected model did not return a final answer. Please try again."

    return reply, totals["prompt_tokens"], totals["reply_tokens"]
