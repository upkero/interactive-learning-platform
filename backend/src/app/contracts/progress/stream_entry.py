"""One decoded Redis Stream entry, suitable for SSE delivery."""

import json
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StreamEntry:
    id: str
    type: str
    data: str

    @classmethod
    def from_redis(cls, entry_id: str | bytes, fields: dict[str | bytes, str | bytes]) -> "StreamEntry":
        raw = fields.get("data", fields.get(b"data", "{}"))
        data = raw.decode() if isinstance(raw, bytes) else raw
        payload = json.loads(data)
        value = entry_id.decode() if isinstance(entry_id, bytes) else entry_id
        return cls(id=value, type=str(payload.get("type", "error")), data=data)
