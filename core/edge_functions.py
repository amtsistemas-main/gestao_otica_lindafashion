"""Calls to the project's Edge Functions with the signed-in user's token.

Privileged work (creating logins, WhatsApp gateway) happens server-side; the desktop app
only sends the user's session token, never a service key.
"""
from __future__ import annotations

import json


class EdgeFunctionError(RuntimeError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def invoke_edge_function(ctx, name: str, payload: dict) -> dict:
    if ctx is None:
        raise EdgeFunctionError("Disponível somente com login no Supabase.")
    client = ctx.client
    headers = {}
    try:
        session = client.auth.get_session()
        if session and session.access_token:
            headers["Authorization"] = f"Bearer {session.access_token}"
    except Exception:
        pass
    try:
        result = client.functions.invoke(name, invoke_options={
            "body": {**payload, "organization_id": ctx.organization_id},
            "headers": headers, "responseType": "json",
        })
    except Exception as exc:
        status = getattr(exc, "status", None)
        message = getattr(exc, "message", None) or str(exc)
        try:
            message = json.loads(message).get("error", message)
        except (ValueError, AttributeError, TypeError):
            pass
        if status == 404 and "not found" in str(message).lower():
            message = f"A função {name} não está publicada no Supabase."
        raise EdgeFunctionError(str(message), status) from exc
    if isinstance(result, (bytes, str)):
        try:
            result = json.loads(result)
        except ValueError:
            result = {}
    if isinstance(result, dict) and result.get("error"):
        raise EdgeFunctionError(str(result["error"]))
    return result if isinstance(result, dict) else {}
