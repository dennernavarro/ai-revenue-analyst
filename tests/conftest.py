import json

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk
from langchain_core.runnables import RunnableLambda
from pydantic import Field


class ScriptedToolModel(GenericFakeChatModel):
    """A chat model that replays fixed scripts.

    GenericFakeChatModel has no bind_tools; our message scripts already
    contain the tool calls, so binding is a no-op. with_structured_output
    replays `structured_outputs` instead (used by the pricing review). This is
    how agent plumbing gets tested offline and deterministically — real-model
    quality belongs to evaluations (Stage 8), not unit tests.
    """

    structured_outputs: list = Field(default_factory=list)

    def bind_tools(self, tools, **kwargs):
        return self

    def with_structured_output(self, schema, **kwargs):
        outputs = iter(self.structured_outputs)
        return RunnableLambda(lambda _input: next(outputs))

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        """GenericFakeChatModel cannot stream tool-call-only messages; emit
        each scripted message as a single chunk instead."""
        message = next(self.messages)
        chunk = AIMessageChunk(
            content=message.content,
            tool_call_chunks=[
                {
                    "name": call["name"],
                    "args": json.dumps(call["args"]),
                    "id": call["id"],
                    "index": i,
                    "type": "tool_call_chunk",
                }
                for i, call in enumerate(getattr(message, "tool_calls", []) or [])
            ],
        )
        yield ChatGenerationChunk(message=chunk)


@pytest.fixture
def scripted_model():
    """Factory fixture: scripted_model([AIMessage(...)], structured=[...])."""

    def factory(messages=(), structured=()) -> ScriptedToolModel:
        return ScriptedToolModel(messages=iter(messages), structured_outputs=list(structured))

    return factory
