from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date


class TimesheetBase(BaseModel):
    employee_id: int
    date: date
    hours: float = Field(..., gt=0, le=24)
    project_tag: str
    description: Optional[str] = None


class TimesheetCreate(TimesheetBase):
    pass


class TimesheetUpdate(BaseModel):
    hours: Optional[float] = Field(None, gt=0, le=24)
    project_tag: Optional[str] = None
    description: Optional[str] = None


class TimesheetResponse(TimesheetBase):
    id: int
    status: str
    tags: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TimesheetListResponse(BaseModel):
    total: int
    items: List[TimesheetResponse]
