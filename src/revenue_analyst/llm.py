"""Model resolution: the LLM vendor is configuration, not code.

Supports every provider string init_chat_model understands
("anthropic:...", "openai:...", "ollama:...") plus a custom
"openrouter:<vendor>/<model>" scheme. OpenRouter speaks the OpenAI API, so it
is just ChatOpenAI pointed at another base_url — one env var
(OPENROUTER_API_KEY) then gives access to hundreds of models.
"""

from __future__ import annotations

import os

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def message_text(message: BaseMessage) -> str:
    """Some providers return content as a list of blocks; flatten to text."""
    if isinstance(message.content, str):
        return message.content
    return "".join(b.get("text", "") for b in message.content if isinstance(b, dict))


def init_model(model: str) -> BaseChatModel:
    if model.startswith("openrouter:"):
        from langchain_openai import ChatOpenAI

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set (see .env.example)")
        return ChatOpenAI(
            model=model.removeprefix("openrouter:"),
            base_url=OPENROUTER_BASE_URL,
            api_key=api_key,
        )
    return init_chat_model(model)
