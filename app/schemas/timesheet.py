from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


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

    model_config = ConfigDict(from_attributes=True)


class TimesheetListResponse(BaseModel):
    total: int
    items: List[TimesheetResponse]
