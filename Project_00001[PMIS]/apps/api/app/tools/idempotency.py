from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .models import IdempotencyLog
import json


def get_idempotent_result(db: Session, idempotency_key: str):
    """Retrieve cached result if idempotency key already processed."""
    log = db.query(IdempotencyLog).filter_by(idempotency_key=idempotency_key).first()
    if log:
        return log.result
    return None


def store_idempotent_result(db: Session, idempotency_key: str, operation: str, result: dict):
    """Store result for idempotency key."""
    log = IdempotencyLog(
        idempotency_key=idempotency_key,
        operation=operation,
        result=result,
    )
    db.add(log)
    try:
        db.commit()
    except IntegrityError:
        # Key already exists, that's ok
        db.rollback()
    return result


def check_idempotency(db: Session, idempotency_key: str, operation: str):
    """
    Check idempotency key and return cached result if exists.
    Returns (is_new, result).
    """
    result = get_idempotent_result(db, idempotency_key)
    if result is not None:
        return False, result
    return True, None
