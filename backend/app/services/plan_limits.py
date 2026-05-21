"""Plan limits and trial checks scoped by Organization."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.organization import Organization
from app.models.search import Search
from app.models.user import User

PLAN_LIMITS = {
    "starter": {"clients": 5, "searches": 20, "users": 3},
    "agency": {"clients": 20, "searches": None, "users": 10},
    "enterprise": {"clients": None, "searches": None, "users": None},
}


def _upgrade_suggestion(plan: str) -> str:
    if plan == "starter":
        return "agency"
    if plan == "agency":
        return "enterprise"
    return "enterprise"


def _plan_limit_detail(
    *,
    limit_type: str,
    current: int,
    max_val: int | None,
    plan: str,
) -> dict:
    return {
        "code": "plan_limit_reached",
        "limit_type": limit_type,
        "current": current,
        "max": max_val,
        "plan": plan,
        "upgrade_to": _upgrade_suggestion(plan),
    }


def check_trial_status(db: Session, organization_id: int) -> None:
    org = db.get(Organization, organization_id)
    if not org:
        return
    if org.plan_status != "trial" or org.trial_ends_at is None:
        return
    if org.trial_ends_at >= datetime.now(timezone.utc):
        return
    raise HTTPException(
        status_code=403,
        detail={
            "code": "trial_expired",
            "plan": org.plan,
            "trial_ends_at": org.trial_ends_at.isoformat() if org.trial_ends_at else None,
        },
    )


def check_client_limit(db: Session, organization_id: int) -> None:
    check_trial_status(db, organization_id)
    org = db.get(Organization, organization_id)
    if not org:
        return
    limits = PLAN_LIMITS.get(org.plan, PLAN_LIMITS["starter"])
    cap = limits["clients"]
    if cap is None:
        return
    current = db.query(func.count(Client.id)).filter(Client.organization_id == organization_id).scalar() or 0
    if current >= cap:
        raise HTTPException(
            status_code=403,
            detail=_plan_limit_detail(limit_type="clients", current=int(current), max_val=cap, plan=org.plan),
        )


def check_search_limit(db: Session, organization_id: int) -> None:
    check_trial_status(db, organization_id)
    org = db.get(Organization, organization_id)
    if not org:
        return
    limits = PLAN_LIMITS.get(org.plan, PLAN_LIMITS["starter"])
    cap = limits["searches"]
    if cap is None:
        return
    current = (
        db.query(func.count(Search.id))
        .join(Client, Search.client_id == Client.id)
        .filter(Client.organization_id == organization_id)
        .scalar()
        or 0
    )
    if current >= cap:
        raise HTTPException(
            status_code=403,
            detail=_plan_limit_detail(limit_type="searches", current=int(current), max_val=cap, plan=org.plan),
        )


def check_user_limit(db: Session, organization_id: int) -> None:
    check_trial_status(db, organization_id)
    org = db.get(Organization, organization_id)
    if not org:
        return
    limits = PLAN_LIMITS.get(org.plan, PLAN_LIMITS["starter"])
    cap = limits["users"]
    if cap is None:
        return
    current = db.query(func.count(User.id)).filter(User.organization_id == organization_id).scalar() or 0
    if current >= cap:
        raise HTTPException(
            status_code=403,
            detail=_plan_limit_detail(limit_type="users", current=int(current), max_val=cap, plan=org.plan),
        )
