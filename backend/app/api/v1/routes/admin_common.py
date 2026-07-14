from __future__ import annotations

from fastapi import Request

from app.services.admin_service import principal_scope_snapshot


def admin_scopes_from_request(request: Request) -> list[str]:
    return principal_scope_snapshot(getattr(request.state, "admin_principal", None))
