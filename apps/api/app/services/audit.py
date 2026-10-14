from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditLog, User


def write_audit(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: str | int | None,
    user: User | None = None,
    request: Request | None = None,
    before: dict | None = None,
    after: dict | None = None,
    details: str | None = None,
) -> AuditLog:
    if details:
        if after is None:
            after = {"details": details}
        elif isinstance(after, dict):
            after["details"] = details

    log = AuditLog(
        user_id=user.id if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        before_json=before,
        after_json=after,
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
    )
    db.add(log)
    return log

