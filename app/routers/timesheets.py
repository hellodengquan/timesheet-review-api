from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date

from app.database import get_db
from app.schemas import (
    TimesheetCreate,
    TimesheetUpdate,
    TimesheetResponse,
    TimesheetListResponse,
)
from app.crud import (
    get_timesheet,
    get_timesheets,
    get_timesheets_count,
    create_timesheet,
    update_timesheet,
    delete_timesheet,
    get_user,
)

router = APIRouter(prefix="/timesheets", tags=["timesheets"])


@router.post("", response_model=TimesheetResponse, status_code=201)
def submit_timesheet(timesheet: TimesheetCreate, db: Session = Depends(get_db)):
    employee = get_user(db, timesheet.employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return create_timesheet(db, timesheet)


@router.get("", response_model=TimesheetListResponse)
def list_timesheets(
    employee_id: Optional[int] = Query(None, description="Filter by employee ID"),
    start_date: Optional[date] = Query(None, description="Start date filter"),
    end_date: Optional[date] = Query(None, description="End date filter"),
    status: Optional[str] = Query(None, description="Filter by status"),
    project_tag: Optional[str] = Query(None, description="Filter by project tag"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    items = get_timesheets(
        db,
        employee_id=employee_id,
        start_date=start_date,
        end_date=end_date,
        status=status,
        project_tag=project_tag,
        skip=skip,
        limit=limit,
    )
    total = get_timesheets_count(
        db,
        employee_id=employee_id,
        start_date=start_date,
        end_date=end_date,
        status=status,
        project_tag=project_tag,
    )
    return TimesheetListResponse(total=total, items=items)


@router.get("/{timesheet_id}", response_model=TimesheetResponse)
def get_single_timesheet(timesheet_id: int, db: Session = Depends(get_db)):
    record = get_timesheet(db, timesheet_id)
    if not record:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    return record


@router.put("/{timesheet_id}", response_model=TimesheetResponse)
def modify_timesheet(
    timesheet_id: int,
    timesheet_update: TimesheetUpdate,
    db: Session = Depends(get_db),
):
    record = update_timesheet(db, timesheet_id, timesheet_update)
    if not record:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    return record


@router.delete("/{timesheet_id}", status_code=204)
def remove_timesheet(timesheet_id: int, db: Session = Depends(get_db)):
    success = delete_timesheet(db, timesheet_id)
    if not success:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    return None
