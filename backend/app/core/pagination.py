"""Opaque cursor helpers for keyset pagination.

A cursor is URL-safe base64 of a small JSON object. Malformed cursors raise a
400 rather than silently restarting from page one.
"""

import base64
import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status


def encode_cursor(**data: Any) -> str:
    def _default(v: Any) -> Any:
        if isinstance(v, datetime):
            return v.isoformat()
        if isinstance(v, uuid.UUID):
            return str(v)
        raise TypeError(type(v))

    return base64.urlsafe_b64encode(
        json.dumps(data, default=_default).encode()
    ).decode()


def decode_cursor(cursor: str, **fields: type) -> dict[str, Any]:
    """Decode a cursor and coerce each named field to the given type.

    Example: decode_cursor(c, t=datetime, id=uuid.UUID)
    """
    try:
        raw = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        out: dict[str, Any] = {}
        for name, typ in fields.items():
            value = raw[name]
            if typ is datetime:
                out[name] = datetime.fromisoformat(value)
            elif typ is uuid.UUID:
                out[name] = uuid.UUID(value)
            else:
                out[name] = typ(value)
        return out
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor"
        ) from None
