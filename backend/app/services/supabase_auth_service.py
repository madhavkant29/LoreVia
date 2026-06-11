from __future__ import annotations

from typing import Any
import uuid

import httpx

from app.core.config import settings


async def delete_supabase_auth_user(supabase_auth_id: uuid.UUID | str | None) -> dict[str, Any]:
    if not supabase_auth_id:
        return {"configured": False, "deleted": False, "followup_required": False}
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        return {"configured": False, "deleted": False, "followup_required": True}

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.delete(
                f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users/{supabase_auth_id}",
                headers={
                    "apikey": settings.SUPABASE_SERVICE_KEY,
                    "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
                },
            )
            if response.status_code == 404:
                return {"configured": True, "deleted": True, "followup_required": False, "not_found": True}
            response.raise_for_status()
    except httpx.HTTPError as exc:
        return {
            "configured": True,
            "deleted": False,
            "followup_required": True,
            "error": str(exc),
        }

    return {"configured": True, "deleted": True, "followup_required": False}
