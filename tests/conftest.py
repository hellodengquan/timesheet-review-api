"""
pytest 共享配置 & fixture
- 使用内存 SQLite 作为测试数据库（避免污染生产数据）
- 每个测试函数独立建表/删表，保证测试隔离
- 覆盖 lifespan 中的 alembic 迁移：在测试中改用 Base.metadata.create_all
- 提供：client, db_session, 预设用户/主管/假日 fixture
"""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db, run_alembic_upgrade_head
from app.models import User, Holiday
from main import app


SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """覆盖 FastAPI 依赖，指向测试用内存数据库"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _override_run_alembic_upgrade_head(revision: str = "head") -> None:
    """
    测试环境中覆盖生产的 alembic upgrade head：
    直接用 Base.metadata 建表（源与 alembic autogenerate 一致），
    避免测试时访问磁盘上的 timesheet.db 或需要 alembic.ini/sqlite 文件路径。
    """
    Base.metadata.create_all(bind=engine)


app.dependency_overrides[get_db] = override_get_db

# 关键：通过 mock monkey-patch，让 main.py lifespan 里的
# run_alembic_upgrade_head 调用在测试期间改为上面的实现
import app.database as _db_module
_db_module.run_alembic_upgrade_head = _override_run_alembic_upgrade_head
# 同时 main.py 已经 import 了这个符号，也需要替换 main 的本地引用
import main as _main_module
_main_module.run_alembic_upgrade_head = _override_run_alembic_upgrade_head


# ---------------------------------------------------------------------------
# 基础 fixture：数据库生命周期 + TestClient
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _db_lifecycle():
    """每个测试函数：建表 -> 执行测试 -> 删表"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> TestClient:
    """返回 FastAPI TestClient，依赖已被覆盖为测试数据库"""
    return TestClient(app)


@pytest.fixture
def db_session():
    """返回一个测试数据库会话，供需要直接操作数据库的 fixture/测试使用"""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# 业务 fixture：预设用户、主管、假日
# ---------------------------------------------------------------------------
@pytest.fixture
def supervisor(db_session) -> User:
    """创建一名主管（role=supervisor, id=1）"""
    sup = User(
        employee_id="SUP-TEST-01",
        name="测试主管",
        email="supervisor@test.com",
        role="supervisor",
        supervisor_id=None,
    )
    db_session.add(sup)
    db_session.commit()
    db_session.refresh(sup)
    return sup


@pytest.fixture
def employee(supervisor, db_session) -> User:
    """创建一名普通员工，其主管为上方 supervisor"""
    emp = User(
        employee_id="EMP-TEST-01",
        name="测试员工A",
        email="employee.a@test.com",
        role="employee",
        supervisor_id=supervisor.id,
    )
    db_session.add(emp)
    db_session.commit()
    db_session.refresh(emp)
    return emp


@pytest.fixture
def employee_b(supervisor, db_session) -> User:
    """创建第二名员工（用于批量审批等跨用户场景）"""
    emp = User(
        employee_id="EMP-TEST-02",
        name="测试员工B",
        email="employee.b@test.com",
        role="employee",
        supervisor_id=supervisor.id,
    )
    db_session.add(emp)
    db_session.commit()
    db_session.refresh(emp)
    return emp


@pytest.fixture
def holiday_date():
    """返回一个固定的、遥远的测试日期，避免与 today 相关逻辑冲突"""
    return date(2030, 5, 1)


@pytest.fixture
def workday_date():
    """返回一个普通的、肯定不是假日的测试日期"""
    return date(2030, 6, 15)


@pytest.fixture
def seeded_holiday(db_session, holiday_date) -> Holiday:
    """预先往 holiday 表中插一条记录（劳动节）"""
    h = Holiday(date=holiday_date, name="测试-劳动节")
    db_session.add(h)
    db_session.commit()
    db_session.refresh(h)
    return h


@pytest.fixture
def other_supervisor(db_session) -> User:
    """另一个独立的主管（用来测试跨主管审批被拒场景）"""
    sup = User(
        employee_id="SUP-TEST-02",
        name="另一位主管",
        email="other.supervisor@test.com",
        role="supervisor",
        supervisor_id=None,
    )
    db_session.add(sup)
    db_session.commit()
    db_session.refresh(sup)
    return sup


@pytest.fixture
def admin(db_session) -> User:
    """创建 admin 角色用户，可审批任意员工"""
    u = User(
        employee_id="ADMIN-TEST-01",
        name="系统管理员",
        email="admin@test.com",
        role="admin",
        supervisor_id=None,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def _create_timesheets_factory(client, employee):
    """返回一个工厂函数，方便创建指定员工在指定日期的工时记录"""

    def _create(emp_id: int, ts_date: date, hours: float, tag: str = "PROJ-TEST"):
        resp = client.post(
            "/api/v1/timesheets",
            json={
                "employee_id": emp_id,
                "date": ts_date.isoformat(),
                "hours": hours,
                "project_tag": tag,
                "description": f"{hours}h on {tag}",
            },
        )
        assert resp.status_code == 201, f"创建工时失败: {resp.status_code} {resp.text}"
        return resp.json()

    return _create
