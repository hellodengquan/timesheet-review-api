from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.schemas import UserCreate, UserResponse
from app.crud import (
    get_user,
    get_user_by_employee_id,
    get_user_by_email,
    get_users,
    create_user,
    get_subordinates,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=201)
def add_user(user: UserCreate, db: Session = Depends(get_db)):
    if get_user_by_employee_id(db, user.employee_id):
        raise HTTPException(
            status_code=400,
            detail=f"Employee ID '{user.employee_id}' already registered",
        )
    if get_user_by_email(db, user.email):
        raise HTTPException(
            status_code=400,
            detail=f"Email '{user.email}' already registered",
        )
    if user.supervisor_id is not None and not get_user(db, user.supervisor_id):
        raise HTTPException(status_code=404, detail="Supervisor not found")
    return create_user(db, user)


@router.get("", response_model=List[UserResponse])
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return get_users(db, skip=skip, limit=limit)


@router.get("/{user_id}", response_model=UserResponse)
def get_single_user(user_id: int, db: Session = Depends(get_db)):
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/employee-id/{employee_id}", response_model=UserResponse)
def get_user_by_emp_id(employee_id: str, db: Session = Depends(get_db)):
    user = get_user_by_employee_id(db, employee_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/{supervisor_id}/subordinates", response_model=List[UserResponse])
def list_subordinates(supervisor_id: int, db: Session = Depends(get_db)):
    supervisor = get_user(db, supervisor_id)
    if not supervisor:
        raise HTTPException(status_code=404, detail="Supervisor not found")
    return get_subordinates(db, supervisor_id)
