"""Placeholder seam for a future fully-native client of this same API.

Not used by the Flask server or the bundled web client today; kept as
scaffolding so a native Android client (see docs on Phase 2) can talk to
``JUSTFITTING_API_BASE_URL`` through one narrow surface instead of the
routes being called ad hoc from multiple places.
"""

from __future__ import annotations

from typing import Optional

from server.src.remote.TokenManager import TokenManager


class RemoteFacade:
    def __init__(self, base_url: str, token_manager: Optional[TokenManager] = None):
        self.base_url = base_url.rstrip("/")
        self.token_manager = token_manager or TokenManager()

    def health(self) -> bool:
        raise NotImplementedError(
            "wire up an HTTP client when a native client needs this"
        )
