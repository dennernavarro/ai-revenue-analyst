import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel


class ScriptedToolModel(GenericFakeChatModel):
    """A chat model that replays a fixed script of AIMessages.

    GenericFakeChatModel has no bind_tools; our scripts already contain the
    tool calls, so binding is a no-op. This is how agent plumbing gets tested
    offline and deterministically — real-model quality belongs to evaluations
    (Stage 8), not unit tests.
    """

    def bind_tools(self, tools, **kwargs):
        return self


@pytest.fixture
def scripted_model():
    """Factory fixture: scripted_model([AIMessage(...), ...]) -> fake model."""

    def factory(messages) -> ScriptedToolModel:
        return ScriptedToolModel(messages=iter(messages))

    return factory
