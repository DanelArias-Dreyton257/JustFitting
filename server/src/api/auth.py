"""Bearer-token auth guard shared by every protected route."""

from __future__ import annotations

from functools import wraps

from flask import current_app, g, jsonify, request


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"error": "missing bearer token"}), 401
        token = header[len("Bearer ") :]
        auth_service = current_app.extensions["auth_service"]
        user_id = auth_service.resolve_token(token)
        if user_id is None:
            return jsonify({"error": "invalid or expired token"}), 401
        g.user_id = user_id
        g.token = token
        return view(*args, **kwargs)

    return wrapped
