from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from app.database import get_db
from app.schemas import (
    ApprovalCreate,
    ApprovalResponse,
    BulkApprovalRequest,
    TimesheetResponse,
)
from app.crud import (
    get_timesheet,
    update_timesheet_status,
    get_approvals_by_timesheet,
    get_approvals_by_approver,
    create_approval,
    get_user,
)

router = APIRouter(prefix="/approvals", tags=["approvals"])

VALID_ACTIONS = {"approved", "rejected"}
VALID_STATUSES = {"approved": "approved", "rejected": "rejected"}


def _validate_action(action: str) -> None:
    if action not in VALID_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action '{action}'. Must be one of: {VALID_ACTIONS}",
        )


def _validate_approver(db: Session, approver_id: int, timesheet_id: int) -> None:
    approver = get_user(db, approver_id)
    if not approver:
        raise HTTPException(status_code=404, detail="Approver not found")
    if approver.role != "supervisor" and approver.role != "admin":
        raise HTTPException(status_code=403, detail="Approver is not authorized")
    timesheet = get_timesheet(db, timesheet_id)
    if timesheet:
        employee = get_user(db, timesheet.employee_id)
        if employee and employee.supervisor_id != approver_id and approver.role != "admin":
            raise HTTPException(
                status_code=403, detail="Approver is not the employee's supervisor"
            )


@router.post("/single", response_model=TimesheetResponse)
def approve_single(approval: ApprovalCreate, db: Session = Depends(get_db)):
    _validate_action(approval.action)
    timesheet = get_timesheet(db, approval.timesheet_id)
    if not timesheet:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    if timesheet.status in {"approved", "rejected"}:
        raise HTTPException(
            status_code=400, detail=f"Timesheet already {timesheet.status}"
        )
    _validate_approver(db, approval.approver_id, approval.timesheet_id)

    new_status = VALID_STATUSES[approval.action]
    updated = update_timesheet_status(db, approval.timesheet_id, new_status)
    create_approval(db, approval)
    return updated


@router.post("/bulk", response_model=dict)
def approve_bulk(bulk_request: BulkApprovalRequest, db: Session = Depends(get_db)):
    _validate_action(bulk_request.action)
    approver = get_user(db, bulk_request.approver_id)
    if not approver:
        raise HTTPException(status_code=404, detail="Approver not found")
    if approver.role != "supervisor" and approver.role != "admin":
        raise HTTPException(status_code=403, detail="Approver is not authorized")

    processed_ids = []
    skipped_ids = []
    failed_ids = []
    new_status = VALID_STATUSES[bulk_request.action]

    for ts_id in bulk_request.timesheet_ids:
        timesheet = get_timesheet(db, ts_id)
        if not timesheet:
            failed_ids.append(ts_id)
            continue
        if timesheet.status in {"approved", "rejected"}:
            skipped_ids.append(ts_id)
            continue
        employee = get_user(db, timesheet.employee_id)
        if employee and employee.supervisor_id != bulk_request.approver_id and approver.role != "admin":
            skipped_ids.append(ts_id)
            continue

        update_timesheet_status(db, ts_id, new_status)
        single_approval = ApprovalCreate(
            timesheet_id=ts_id,
            approver_id=bulk_request.approver_id,
            action=bulk_request.action,
            comment=bulk_request.comment,
        )
        create_approval(db, single_approval)
        processed_ids.append(ts_id)

    return {
        "total": len(bulk_request.timesheet_ids),
        "processed": processed_ids,
        "processed_count": len(processed_ids),
        "skipped": skipped_ids,
        "skipped_count": len(skipped_ids),
        "failed": failed_ids,
        "failed_count": len(failed_ids),
    }


@router.get("/history/{timesheet_id}", response_model=List[ApprovalResponse])
def get_timesheet_history(timesheet_id: int, db: Session = Depends(get_db)):
    timesheet = get_timesheet(db, timesheet_id)
    if not timesheet:
        raise HTTPException(status_code=404, detail="Timesheet not found")
    return get_approvals_by_timesheet(db, timesheet_id)


@router.get("/approver/{approver_id}", response_model=List[ApprovalResponse])
def get_approver_history(
    approver_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    approver = get_user(db, approver_id)
    if not approver:
        raise HTTPException(status_code=404, detail="Approver not found")
    return get_approvals_by_approver(db, approver_id, skip=skip, limit=limit)
