from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models import ApprovalRecord, Holiday
from app.schemas import ApprovalCreate, HolidayCreate


def get_approval(db: Session, approval_id: int) -> Optional[ApprovalRecord]:
    return db.query(ApprovalRecord).filter(ApprovalRecord.id == approval_id).first()


def get_approvals_by_timesheet(db: Session, timesheet_id: int) -> List[ApprovalRecord]:
    return (
        db.query(ApprovalRecord)
        .filter(ApprovalRecord.timesheet_id == timesheet_id)
        .order_by(ApprovalRecord.created_at.desc())
        .all()
    )


def get_approvals_by_approver(db: Session, approver_id: int, skip: int = 0, limit: int = 100) -> List[ApprovalRecord]:
    return (
        db.query(ApprovalRecord)
        .filter(ApprovalRecord.approver_id == approver_id)
        .order_by(ApprovalRecord.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_approval(db: Session, approval: ApprovalCreate) -> ApprovalRecord:
    db_approval = ApprovalRecord(
        timesheet_id=approval.timesheet_id,
        approver_id=approval.approver_id,
        action=approval.action,
        comment=approval.comment,
    )
    db.add(db_approval)
    db.commit()
    db.refresh(db_approval)
    return db_approval


def get_holiday(db: Session, holiday_id: int) -> Optional[Holiday]:
    return db.query(Holiday).filter(Holiday.id == holiday_id).first()


def get_holiday_by_date(db: Session, holiday_date: date) -> Optional[Holiday]:
    return db.query(Holiday).filter(Holiday.date == holiday_date).first()


def get_holidays(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[Holiday]:
    query = db.query(Holiday)
    if start_date is not None:
        query = query.filter(Holiday.date >= start_date)
    if end_date is not None:
        query = query.filter(Holiday.date <= end_date)
    return query.order_by(Holiday.date.asc()).offset(skip).limit(limit).all()


def create_holiday(db: Session, holiday: HolidayCreate) -> Holiday:
    db_holiday = Holiday(date=holiday.date, name=holiday.name)
    db.add(db_holiday)
    db.commit()
    db.refresh(db_holiday)
    return db_holiday


def delete_holiday(db: Session, holiday_id: int) -> bool:
    db_holiday = get_holiday(db, holiday_id)
    if not db_holiday:
        return False
    db.delete(db_holiday)
    db.commit()
    return True
