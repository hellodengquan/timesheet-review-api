import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# 数据库 URL：
#   本地开发默认为 sqlite:///./timesheet.db
#   容器/K8s 中通过 DB_PATH 环境变量覆盖（例如 /data/timesheet.db）
_DB_PATH = os.environ.get("DB_PATH", "./timesheet.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{_DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI 依赖注入：每个请求分配一个 Session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_alembic_upgrade_head(revision: str = "head") -> None:
    """
    通过 Alembic Python API 执行迁移（alembic upgrade <revision>）。

    调用时机：
      - FastAPI lifespan 启动钩子中（服务启动时自动执行）
      - seed.py 种子脚本执行前（保证表结构存在）
      - 测试框架需要时
    """
    # 延迟导入：模块加载阶段不强制依赖 alembic 初始化
    from alembic import command
    from alembic.config import Config as AlembicConfig

    # 构造 Alembic 配置（指向仓库根的 alembic.ini）
    ini_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "alembic.ini",
    )
    alembic_cfg = AlembicConfig(ini_path)

    # 把 DB_PATH 再注入到 alembic 配置里，确保 env.py 读取到一致的路径
    alembic_cfg.set_main_option("sqlalchemy.url", SQLALCHEMY_DATABASE_URL)

    # 执行迁移
    command.upgrade(alembic_cfg, revision)
