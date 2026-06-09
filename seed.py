"""
最小化种子数据脚本 (seed.py)

运行方式:
    python seed.py
"""
import sys
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.database import engine, Base, SessionLocal
from app.models import User, Timesheet, ApprovalRecord, Holiday
from app.schemas import TimesheetCreate
from app.crud import create_timesheet


def seed_users(db: Session) -> dict:
    users = {}
    if db.query(User).count() > 0:
        print("[跳过] 表 users 中已有数据，跳过用户种子。")
        for u in db.query(User).all():
            users[u.employee_id] = u.id
        return users

    users_data = [
        {
            "employee_id": "SUP001",
            "name": "张明主管",
            "email": "zhang.ming@example.com",
            "role": "supervisor",
            "supervisor_id": None,
        },
        {
            "employee_id": "EMP001",
            "name": "李华",
            "email": "li.hua@example.com",
            "role": "employee",
            "supervisor_id": 1,
        },
        {
            "employee_id": "EMP002",
            "name": "王芳",
            "email": "wang.fang@example.com",
            "role": "employee",
            "supervisor_id": 1,
        },
    ]

    for data in users_data:
        u = User(**data)
        db.add(u)
        db.flush()
        users[u.employee_id] = u.id

    db.commit()
    print(f"[完成] 已插入 {len(users_data)} 条用户数据。")
    return users


def seed_holidays(db: Session) -> None:
    if db.query(Holiday).count() > 0:
        print("[跳过] 表 holidays 中已有数据，跳过节假种子。")
        return

    today = date.today()
    this_saturday = today - timedelta(days=today.weekday()) + timedelta(days=5)
    holidays = [
        {"date": this_saturday, "name": "周末"},
        {"date": today + timedelta(days=7), "name": "公司纪念日"},
    ]
    for data in holidays:
        db.add(Holiday(**data))
    db.commit()
    print(f"[完成] 已插入 {len(holidays)} 条法定/公司假日。")


def seed_timesheets(db: Session, user_map: dict) -> None:
    if db.query(Timesheet).count() > 0:
        print("[跳过] 表 timesheets 中已有数据，跳过工时种子。")
        return

    today = date.today()
    emp1 = user_map["EMP001"]
    emp2 = user_map["EMP002"]
    data = [
        {"employee_id": emp1, "date": today, "hours": 8, "project_tag": "PROJ-A", "description": "需求评审"},
        {"employee_id": emp1, "date": today, "hours": 5, "project_tag": "PROJ-B", "description": "开发任务"},
        {"employee_id": emp2, "date": today - timedelta(days=1), "hours": 9, "project_tag": "PROJ-A", "description": "代码评审"},
        {"employee_id": emp2, "date": today - timedelta(days=2), "hours": 7, "project_tag": "PROJ-C", "description": "测试任务"},
    ]
    inserted = 0
    for d in data:
        ts_in = TimesheetCreate(**d)
        create_timesheet(db, ts_in)
        inserted += 1
    db.commit()
    print(f"[完成] 已插入 {inserted} 条工时记录（其中含累计超过12小时触发 anomaly 的样例）。")


def run() -> None:
    print("=" * 50)
    print("开始执行种子数据脚本 ...")
    print("=" * 50)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user_map = seed_users(db)
        seed_holidays(db)
        seed_timesheets(db, user_map)
    except Exception as exc:
        db.rollback()
        print(f"[错误] 种子脚本执行失败: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()

    print("=" * 50)
    print("种子数据执行完成！")
    print("=" * 50)


if __name__ == "__main__":
    run()
