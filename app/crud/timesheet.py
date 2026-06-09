from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date

from app.models import Timesheet, Holiday
from app.schemas import TimesheetCreate, TimesheetUpdate


def get_timesheet(db: Session, timesheet_id: int) -> Optional[Timesheet]:
    return db.query(Timesheet).filter(Timesheet.id == timesheet_id).first()


def get_timesheets(
    db: Session,
    employee_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    status: Optional[str] = None,
    project_tag: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[Timesheet]:
    query = db.query(Timesheet)
    if employee_id is not None:
        query = query.filter(Timesheet.employee_id == employee_id)
    if start_date is not None:
        query = query.filter(Timesheet.date >= start_date)
    if end_date is not None:
        query = query.filter(Timesheet.date <= end_date)
    if status is not None:
        query = query.filter(Timesheet.status == status)
    if project_tag is not None:
        query = query.filter(Timesheet.project_tag == project_tag)
    return query.order_by(Timesheet.date.desc()).offset(skip).limit(limit).all()


def get_timesheets_count(
    db: Session,
    employee_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    status: Optional[str] = None,
    project_tag: Optional[str] = None,
) -> int:
    query = db.query(Timesheet)
    if employee_id is not None:
        query = query.filter(Timesheet.employee_id == employee_id)
    if start_date is not None:
        query = query.filter(Timesheet.date >= start_date)
    if end_date is not None:
        query = query.filter(Timesheet.date <= end_date)
    if status is not None:
        query = query.filter(Timesheet.status == status)
    if project_tag is not None:
        query = query.filter(Timesheet.project_tag == project_tag)
    return query.count()


def get_daily_total_hours(db: Session, employee_id: int, target_date: date) -> float:
    records = (
        db.query(Timesheet)
        .filter(Timesheet.employee_id == employee_id, Timesheet.date == target_date)
        .all()
    )
    return sum(r.hours for r in records)


def is_holiday(db: Session, target_date: date) -> Optional[Holiday]:
    return db.query(Holiday).filter(Holiday.date == target_date).first()


def _detect_anomaly(
    db: Session, employee_id: int, target_date: date, current_hours: float
) -> List[str]:
    tags = []
    daily_total = get_daily_total_hours(db, employee_id, target_date) + current_hours
    if daily_total > 12:
        tags.append("anomaly")
    if is_holiday(db, target_date):
        if "anomaly" not in tags:
            tags.append("anomaly")
    return tags


def create_timesheet(db: Session, timesheet: TimesheetCreate) -> Timesheet:
    anomaly_tags = _detect_anomaly(db, timesheet.employee_id, timesheet.date, timesheet.hours)
    db_timesheet = Timesheet(
        employee_id=timesheet.employee_id,
        date=timesheet.date,
        hours=timesheet.hours,
        project_tag=timesheet.project_tag,
        description=timesheet.description,
        status="pending",
        tags=",".join(anomaly_tags) if anomaly_tags else "",
    )
    db.add(db_timesheet)
    db.commit()
    db.refresh(db_timesheet)
    return db_timesheet


def update_timesheet(
    db: Session, timesheet_id: int, timesheet_update: TimesheetUpdate
) -> Optional[Timesheet]:
    db_timesheet = get_timesheet(db, timesheet_id)
    if not db_timesheet:
        return None
    update_data = timesheet_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_timesheet, key, value)
    if "hours" in update_data or "date" in update_data:
        new_tags = _detect_anomaly(
            db, db_timesheet.employee_id, db_timesheet.date, 0.0
        )
        current_tags = [t for t in (db_timesheet.tags or "").split(",") if t]
        for tag in new_tags:
            if tag not in current_tags:
                current_tags.append(tag)
        db_timesheet.tags = ",".join(current_tags)
    db.commit()
    db.refresh(db_timesheet)
    return db_timesheet


def update_timesheet_status(
    db: Session, timesheet_id: int, status: str
) -> Optional[Timesheet]:
    db_timesheet = get_timesheet(db, timesheet_id)
    if not db_timesheet:
        return None
    db_timesheet.status = status
    db.commit()
    db.refresh(db_timesheet)
    return db_timesheet


def get_anomaly_timesheets(
    db: Session,
    employee_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[Timesheet]:
    query = db.query(Timesheet).filter(Timesheet.tags.contains("anomaly"))
    if employee_id is not None:
        query = query.filter(Timesheet.employee_id == employee_id)
    if start_date is not None:
        query = query.filter(Timesheet.date >= start_date)
    if end_date is not None:
        query = query.filter(Timesheet.date <= end_date)
    return query.order_by(Timesheet.date.desc()).offset(skip).limit(limit).all()


def delete_timesheet(db: Session, timesheet_id: int) -> bool:
    db_timesheet = get_timesheet(db, timesheet_id)
    if not db_timesheet:
        return False
    db.delete(db_timesheet)
    db.commit()
    return True
