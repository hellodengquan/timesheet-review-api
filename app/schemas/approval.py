from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date


class ApprovalBase(BaseModel):
    timesheet_id: int
    approver_id: int
    action: str
    comment: Optional[str] = None


class ApprovalCreate(ApprovalBase):
    pass


class ApprovalResponse(ApprovalBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class BulkApprovalRequest(BaseModel):
    timesheet_ids: List[int]
    approver_id: int
    action: str
    comment: Optional[str] = None


class HolidayBase(BaseModel):
    date: date
    name: str


class HolidayCreate(HolidayBase):
    pass


class HolidayResponse(HolidayBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
