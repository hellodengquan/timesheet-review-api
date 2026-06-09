from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from app.database import get_db
from app.schemas import TimesheetResponse, HolidayCreate, HolidayResponse, TimesheetListResponse
from app.crud import (
    get_anomaly_timesheets,
    get_timesheets_count,
    get_holiday,
    get_holiday_by_date,
    get_holidays,
    create_holiday,
    delete_holiday,
)

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


@router.get("", response_model=TimesheetListResponse)
def list_anomaly_timesheets(
    employee_id: Optional[int] = Query(None, description="Filter by employee ID"),
    start_date: Optional[date] = Query(None, description="Start date filter"),
    end_date: Optional[date] = Query(None, description="End date filter"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    items = get_anomaly_timesheets(
        db,
        employee_id=employee_id,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
    )
    return TimesheetListResponse(total=len(items), items=items)


@router.get("/holidays", response_model=List[HolidayResponse])
def list_holidays(
    start_date: Optional[date] = Query(None, description="Start date filter"),
    end_date: Optional[date] = Query(None, description="End date filter"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return get_holidays(db, start_date=start_date, end_date=end_date, skip=skip, limit=limit)


@router.post("/holidays", response_model=HolidayResponse, status_code=201)
def add_holiday(holiday: HolidayCreate, db: Session = Depends(get_db)):
    existing = get_holiday_by_date(db, holiday.date)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Holiday for date {holiday.date} already exists: {existing.name}",
        )
    return create_holiday(db, holiday)


@router.delete("/holidays/{holiday_id}", status_code=204)
def remove_holiday(holiday_id: int, db: Session = Depends(get_db)):
    success = delete_holiday(db, holiday_id)
    if not success:
        raise HTTPException(status_code=404, detail="Holiday not found")
    return None
