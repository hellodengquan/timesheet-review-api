from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


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

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)
