import json
import uuid
from typing import Any


def book_cache_access_key(current_user_id: uuid.UUID, collaborator: Any | None) -> str:
    """Build a stable cache partition key for an owner's or collaborator's access."""
    if collaborator is None:
        return f"owner:{current_user_id}"
    permissions = collaborator.permissions if isinstance(collaborator.permissions, dict) else {}
    return "||".join(
        [
            f"user:{current_user_id}",
            f"role:{collaborator.role}",
            f"scope:{json.dumps(collaborator.scope, sort_keys=True, default=str)}",
            f"permissions:{json.dumps(permissions, sort_keys=True, default=str)}",
        ]
    )
