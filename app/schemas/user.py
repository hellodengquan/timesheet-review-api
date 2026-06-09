from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from datetime import datetime, date


class UserBase(BaseModel):
    employee_id: str
    name: str
    email: EmailStr
    role: str = "employee"
    supervisor_id: Optional[int] = None


class UserCreate(UserBase):
    pass


class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
