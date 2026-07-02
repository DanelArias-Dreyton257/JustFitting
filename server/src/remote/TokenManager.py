"""Placeholder seam for a future fully-native client's token storage.

Today the web client keeps its bearer token in ``localStorage`` (see
client/src/webapp/static/js/session.js). A native client talking to this
same API would need an equivalent secure, platform-appropriate store; this
stub documents that contract so it stays a first-class concern.
"""

from __future__ import annotations

from typing import Optional


class TokenManager:
    def __init__(self):
        self._token: Optional[str] = None

    def get_token(self) -> Optional[str]:
        return self._token

    def set_token(self, token: str) -> None:
        self._token = token

    def clear(self) -> None:
        self._token = None
