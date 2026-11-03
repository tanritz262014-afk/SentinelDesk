"""Detection rule settings: list and tune thresholds."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.detection.engine import RULE_METADATA
from app.models import DetectionRule
from app.schemas import RuleOut, RuleUpdate

router = APIRouter(prefix="/api/rules", tags=["rules"])


def to_rule_out(rule: DetectionRule) -> RuleOut:
    meta = RULE_METADATA.get(rule.id, {"category": "Other", "uses_threshold": False, "uses_window": False})
    return RuleOut(
        id=rule.id,
        name=rule.name,
        description=rule.description,
        enabled=rule.enabled,
        severity=rule.severity,
        threshold=rule.threshold,
        window_minutes=rule.window_minutes,
        mitre_technique=rule.mitre_technique,
        limitations=rule.limitations,
        false_positives=rule.false_positives,
        updated_at=rule.updated_at,
        **meta,
    )


@router.get("", response_model=list[RuleOut])
def list_rules(db: Session = Depends(get_db)):
    return [to_rule_out(r) for r in db.scalars(select(DetectionRule).order_by(DetectionRule.id))]


@router.put("/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: str, changes: RuleUpdate, db: Session = Depends(get_db)):
    """Change a rule's settings. New values apply to logs uploaded afterwards."""
    rule = db.get(DetectionRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    meta = RULE_METADATA.get(rule.id, {})
    if changes.threshold is not None and not meta.get("uses_threshold"):
        raise HTTPException(status_code=422, detail=f"{rule.id} does not use a threshold")
    if changes.window_minutes is not None and not meta.get("uses_window"):
        raise HTTPException(status_code=422, detail=f"{rule.id} does not use a time window")

    for field_name, value in changes.model_dump(exclude_none=True).items():
        setattr(rule, field_name, value)
    db.commit()
    db.refresh(rule)
    return to_rule_out(rule)
