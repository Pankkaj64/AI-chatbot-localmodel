from openai import AsyncOpenAI

from config import Config

# Ollama speaks the OpenAI API; the SDK requires a key but Ollama ignores it
client = AsyncOpenAI(base_url=Config.LLM_BASE_URL, api_key="ollama")

SAFETY_PROMPT = (
    "Classify the user text as unsafe if it contains hate, harassment, self-harm, "
    "sexual content involving minors, or violence instructions. "
    "Respond only with 'SAFE' or 'UNSAFE: <category>'."
)
BIAS_PROMPT = (
    "Analyze the following text for racial, gender, or cultural bias. "
    "Respond only with 'BIASED' or 'CLEAN'."
)


async def check_safety(text: str) -> tuple[bool, list[str]]:
    """Asks the local model whether the text is safe. Returns (is_safe, flagged_categories)."""
    check = await client.chat.completions.create(
        model=Config.LLM_MODEL,
        messages=[{"role": "system", "content": SAFETY_PROMPT}, {"role": "user", "content": text}],
        max_tokens=10,
    )
    out = check.choices[0].message.content.strip().upper()
    if out.startswith("UNSAFE"):
        return False, [out.split(":", 1)[-1].strip().lower() or "unsafe"]
    return True, []


async def detect_bias(text: str) -> bool:
    """Returns True if the local model judges the text to contain racial, gender, or cultural bias."""
    check = await client.chat.completions.create(
        model=Config.LLM_MODEL,
        messages=[{"role": "system", "content": BIAS_PROMPT}, {"role": "user", "content": text}],
        max_tokens=5,
    )
    return "BIASED" in check.choices[0].message.content.upper()


async def generate_reply(model: str, messages: list[dict]) -> tuple[str, int, int]:
    """Generates the assistant reply. Returns (reply_text, prompt_tokens, reply_tokens)."""
    response = await client.chat.completions.create(model=model, messages=messages)
    usage = response.usage
    return (
        response.choices[0].message.content,
        usage.prompt_tokens if usage else 0,
        usage.completion_tokens if usage else 0,
    )
