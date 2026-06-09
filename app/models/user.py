from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    role = Column(String(20), nullable=False, default="employee")
    supervisor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    supervisor = relationship("User", remote_side=[id], backref="subordinates")
    timesheets = relationship("Timesheet", back_populates="employee")
    approvals = relationship("ApprovalRecord", back_populates="approver", foreign_keys="ApprovalRecord.approver_id")
