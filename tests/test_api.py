"""API tests run fully offline: the REST endpoints never touch the LLM, and
the /chat endpoint gets a scripted fake model via the create_app factory."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

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
    app = create_app(pms=MockPMS(DATA_DIR), model=scripted_model(script))
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
