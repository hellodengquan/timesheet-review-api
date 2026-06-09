from sqlalchemy.orm import Session
from typing import Optional, List

from app.models import User
from app.schemas import UserCreate


def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_employee_id(db: Session, employee_id: str) -> Optional[User]:
    return db.query(User).filter(User.employee_id == employee_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    return db.query(User).offset(skip).limit(limit).all()


def get_subordinates(db: Session, supervisor_id: int) -> List[User]:
    return db.query(User).filter(User.supervisor_id == supervisor_id).all()


def create_user(db: Session, user: UserCreate) -> User:
    db_user = User(
        employee_id=user.employee_id,
        name=user.name,
        email=user.email,
        role=user.role,
        supervisor_id=user.supervisor_id,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user
