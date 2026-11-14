import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
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


@pytest.fixture
def scripted_model():
    """Factory fixture: scripted_model([AIMessage(...)], structured=[...])."""

    def factory(messages=(), structured=()) -> ScriptedToolModel:
        return ScriptedToolModel(messages=iter(messages), structured_outputs=list(structured))

    return factory
