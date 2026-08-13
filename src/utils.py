"""Shared utilities: LLM client creation, JSON parsing, prompt loading."""
import json
import re
from pathlib import Path
from types import SimpleNamespace


class AzureAnthropicClient:
    """Configuration for Azure's Anthropic Messages REST endpoint."""

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        api_version: str,
        max_tokens: int,
    ) -> None:
        endpoint = endpoint.rstrip("/")
        if endpoint.endswith("/anthropic"):
            endpoint += "/v1/messages"
        self.endpoint = endpoint
        self.api_key = api_key
        self.api_version = api_version
        self.max_tokens = max(1, max_tokens)


def load_prompt(filename: str) -> str:
    prompts_dir = Path(__file__).parent.parent / "prompts"
    path = prompts_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def get_llm_client():
    """
    Return the configured LLM client and model/deployment name.

    Supported providers: azure_anthropic, azure_openai, and openai.
    """
    from src.config import (
        AZURE_ANTHROPIC_API_KEY,
        AZURE_ANTHROPIC_API_VERSION,
        AZURE_ANTHROPIC_ENDPOINT,
        AZURE_ANTHROPIC_MAX_TOKENS,
        AZURE_ANTHROPIC_MODEL,
        AZURE_OPENAI_ENDPOINT,
        AZURE_OPENAI_API_KEY,
        AZURE_OPENAI_DEPLOYMENT_NAME,
        AZURE_OPENAI_API_VERSION,
        LLM_PROVIDER,
        OPENAI_API_KEY,
        OPENAI_MODEL,
    )

    provider = LLM_PROVIDER.replace("-", "_")

    if provider in ("azure_anthropic", "anthropic", "claude"):
        missing = [
            name
            for name, value in (
                ("AZURE_ANTHROPIC_ENDPOINT", AZURE_ANTHROPIC_ENDPOINT),
                ("AZURE_ANTHROPIC_API_KEY", AZURE_ANTHROPIC_API_KEY),
                ("AZURE_ANTHROPIC_MODEL", AZURE_ANTHROPIC_MODEL),
            )
            if not value
        ]
        if missing:
            raise EnvironmentError(
                "Missing Azure Anthropic configuration: " + ", ".join(missing)
            )
        return (
            AzureAnthropicClient(
                endpoint=AZURE_ANTHROPIC_ENDPOINT,
                api_key=AZURE_ANTHROPIC_API_KEY,
                api_version=AZURE_ANTHROPIC_API_VERSION,
                max_tokens=AZURE_ANTHROPIC_MAX_TOKENS,
            ),
            AZURE_ANTHROPIC_MODEL,
        )

    if provider in ("", "auto", "azure_openai") and AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY:
        from openai import AzureOpenAI
        client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
        )
        deployment = AZURE_OPENAI_DEPLOYMENT_NAME or "gpt-4o"
        return client, deployment

    if provider in ("", "auto", "openai") and OPENAI_API_KEY:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        return client, OPENAI_MODEL or "gpt-4o"

    if provider and provider not in ("auto", "azure_openai", "openai"):
        raise EnvironmentError(f"Unsupported LLM_PROVIDER: {LLM_PROVIDER}")

    raise EnvironmentError(
        "No credentials found for the configured LLM provider."
    )


def _anthropic_chat_completion(client: AzureAnthropicClient, **kwargs):
    """Translate the app's OpenAI-style arguments to Anthropic Messages REST."""
    import httpx

    system_parts: list[str] = []
    messages: list[dict[str, str]] = []
    for item in kwargs.get("messages", []):
        role = str(item.get("role", "user"))
        content = item.get("content", "")
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        if role == "system":
            if content.strip():
                system_parts.append(content)
            continue
        if role not in ("user", "assistant"):
            role = "user"
        messages.append({"role": role, "content": content})

    if not messages:
        raise ValueError("Anthropic Messages API requires at least one user message.")

    payload = {
        "model": kwargs["model"],
        "messages": messages,
        "max_tokens": int(kwargs.get("max_tokens") or client.max_tokens),
    }
    if system_parts:
        payload["system"] = "\n\n".join(system_parts)
    if kwargs.get("temperature") is not None:
        payload["temperature"] = kwargs["temperature"]
    if kwargs.get("top_p") is not None:
        payload["top_p"] = kwargs["top_p"]
    if kwargs.get("stop"):
        stop = kwargs["stop"]
        payload["stop_sequences"] = stop if isinstance(stop, list) else [stop]

    response = httpx.post(
        client.endpoint,
        headers={
            "Content-Type": "application/json",
            "x-api-key": client.api_key,
            "anthropic-version": client.api_version,
        },
        json=payload,
        timeout=180.0,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = response.text[:1000].strip()
        raise RuntimeError(
            f"Azure Anthropic request failed ({response.status_code}): {detail}"
        ) from exc

    data = response.json()
    text = "".join(
        str(block.get("text", ""))
        for block in data.get("content", [])
        if block.get("type") == "text"
    )
    usage = data.get("usage") or {}
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(
            prompt_tokens=int(usage.get("input_tokens", 0) or 0),
            completion_tokens=int(usage.get("output_tokens", 0) or 0),
        ),
    )


def llm_chat_completion(client, **kwargs):
    """
    Call the configured provider and append one Excel row for this call.
    Usage includes system prompts (.md), user content, and model output.
    """
    if isinstance(client, AzureAnthropicClient):
        response = _anthropic_chat_completion(client, **kwargs)
    else:
        response = client.chat.completions.create(**kwargs)
    usage = getattr(response, "usage", None)
    if usage is not None:
        from src.token_tracker import record_usage

        record_usage(
            getattr(usage, "prompt_tokens", 0) or 0,
            getattr(usage, "completion_tokens", 0) or 0,
        )
    return response


def parse_json_response(raw: str) -> dict:
    """
    Safely parse JSON from LLM response.
    Handles cases where the model wraps JSON in markdown code fences.
    """
    # Strip markdown fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()

    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try to extract the first JSON object in the string
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"LLM returned invalid JSON. Raw response (first 500 chars):\n{raw[:500]}"
    )
