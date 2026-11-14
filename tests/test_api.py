"""API tests run fully offline: the REST endpoints never touch the LLM, and
the /chat endpoint gets a scripted fake model via the create_app factory."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from revenue_analyst.api import create_app
from revenue_analyst.pms.mock import MockPMS

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture
def client(scripted_model):
    script = [
        AIMessage(
            content="",
            tool_calls=[
                {"name": "list_properties", "args": {}, "id": "call_1", "type": "tool_call"}
            ],
        ),
        AIMessage(content="We manage 3 properties."),
        AIMessage(content="You asked how many properties we manage."),
    ]
    app = create_app(
        pms=MockPMS(DATA_DIR), model=scripted_model(script), checkpointer=InMemorySaver()
    )
    return TestClient(app)


def test_list_properties(client):
    response = client.get("/properties")
    assert response.status_code == 200
    assert {p["property_id"] for p in response.json()} == {
        "seaside-villa",
        "urban-boutique",
        "mountain-cabins",
    }


def test_performance_endpoint(client):
    response = client.get(
        "/properties/seaside-villa/performance",
        params={"start": "2026-08-01", "end": "2026-09-01"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["nights_available"] == 31
    assert body["adr"] == pytest.approx(510.0)


def test_calendar_endpoint(client):
    response = client.get(
        "/properties/urban-boutique/calendar",
        params={"start": "2026-12-01", "end": "2027-01-01"},
    )
    assert response.status_code == 200
    days = response.json()
    assert len(days) == 31
    assert all(d["capacity"] == 12 and d["rate"] > 0 for d in days)


def test_room_types_endpoint(client):
    response = client.get(
        "/properties/urban-boutique/room-types",
        params={"start": "2026-12-01", "end": "2027-01-01"},
    )
    assert response.status_code == 200
    rows = response.json()
    assert {r["name"] for r in rows} == {"Standard Queen", "Deluxe King", "Corner Suite"}
    assert sum(r["units"] for r in rows) == 12
    suite = next(r for r in rows if r["name"] == "Corner Suite")
    assert suite.get("from_rate") > 0


def test_pace_endpoint(client):
    response = client.get(
        "/properties/mountain-cabins/pace",
        params={"start": "2026-12-01", "end": "2027-01-01"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["capacity_nights"] == 4 * 31
    assert len(body["pace"]) == 4


def test_unknown_property_is_404(client):
    response = client.get(
        "/properties/nope/performance", params={"start": "2026-08-01", "end": "2026-09-01"}
    )
    assert response.status_code == 404


def test_inverted_range_is_400(client):
    response = client.get(
        "/properties/seaside-villa/performance",
        params={"start": "2026-09-01", "end": "2026-08-01"},
    )
    assert response.status_code == 400


def test_review_approval_flow(scripted_model):
    from revenue_analyst.agents.pricing_review import RateProposal

    model = scripted_model(
        structured=[RateProposal(adjustment_pct=-10, rationale="slow", expected_effect="pickup")]
    )
    app = create_app(pms=MockPMS(DATA_DIR), model=model, checkpointer=InMemorySaver())
    review_client = TestClient(app)

    started = review_client.post(
        "/reviews",
        json={"property_id": "mountain-cabins", "start": "2026-12-01", "end": "2027-01-01"},
    ).json()
    assert started["status"] == "pending_approval"
    assert started["proposal"]["adjustment_pct"] == -10

    decided = review_client.post(
        f"/reviews/{started['review_id']}/decision", json={"approved": True}
    ).json()
    assert decided["status"] == "completed"
    assert decided["outcome"].startswith("APPROVED")

    # deciding twice → conflict; unknown review → not found
    again = review_client.post(
        f"/reviews/{started['review_id']}/decision", json={"approved": True}
    )
    assert again.status_code == 409
    missing = review_client.post("/reviews/nope/decision", json={"approved": True})
    assert missing.status_code == 404


def test_chat_input_injects_selected_property_context():
    from revenue_analyst.api import ChatRequest, _chat_input

    pms = MockPMS(DATA_DIR)
    plain = ChatRequest(message="How was August here?")
    assert _chat_input(pms, plain) == "How was August here?"

    selected = ChatRequest(message="How was August here?", property_id="seaside-villa")
    contextualized = _chat_input(pms, selected)
    assert contextualized.startswith("[Dashboard context:")
    assert "Seaside Villa" in contextualized
    assert contextualized.endswith("How was August here?")

    unknown = ChatRequest(message="hi", property_id="nope")
    assert _chat_input(pms, unknown) == "hi"


def test_chat_stream_emits_tool_token_and_done_events(client):
    response = client.post("/chat/stream", json={"message": "How many properties?"})
    assert response.status_code == 200
    events = [
        __import__("json").loads(line[len("data: ") :])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    kinds = [e["type"] for e in events]
    assert kinds[0] == "start" and kinds[-1] == "done"
    assert any(e["type"] == "tool" and e["name"] == "list_properties" for e in events)
    reply = "".join(e["text"] for e in events if e["type"] == "token")
    assert "3 properties" in reply


def test_chat_keeps_conversation_memory(client):
    first = client.post("/chat", json={"message": "How many properties?"}).json()
    assert first["reply"] == "We manage 3 properties."
    assert first["tool_calls"] == [{"name": "list_properties", "args": {}}]

    second = client.post(
        "/chat",
        json={"message": "What did I ask?", "conversation_id": first["conversation_id"]},
    ).json()
    assert second["conversation_id"] == first["conversation_id"]
    assert second["reply"] == "You asked how many properties we manage."
    assert second["tool_calls"] == []
