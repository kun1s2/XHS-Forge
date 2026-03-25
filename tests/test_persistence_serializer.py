from app.agents.runtime.supervisor_runtime import SupervisorStructuredResponse
from app.core.persistence import SERIALIZER_MSGPACK_ALLOWLIST
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer


def test_supervisor_structured_response_is_allowlisted_for_msgpack() -> None:
    serializer = JsonPlusSerializer().with_msgpack_allowlist(SERIALIZER_MSGPACK_ALLOWLIST)
    payload = {
        "reply": "已更新购买决策档案。",
        "next_step": "继续补充图片证据。",
        "turn_outcome": "updated_note",
    }

    encoded = serializer.dumps_typed(payload)
    decoded = serializer.loads_typed(encoded)

    assert isinstance(decoded, dict)
    assert decoded["reply"] == payload["reply"]
    assert decoded["next_step"] == payload["next_step"]
    assert decoded["turn_outcome"] == payload["turn_outcome"]
