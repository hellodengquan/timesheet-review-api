"""
Alembic environment configuration
---------------------------------
关键点：
  1. 通过环境变量 DB_PATH 控制 SQLite 路径，与 app/database.py 保持一致
  2. 从 app.models 加载 Base.metadata，支持 autogenerate
  3. SQLite 开启 render_as_batch=True（兼容 ALTER TABLE 场景）
  4. 线上迁移命令：alembic upgrade head
"""
from logging.config import fileConfig
import os

from sqlalchemy import engine_from_config, pool
from alembic import context

# 保证 app 包可被 import（alembic.ini 中 prepend_sys_path=. 也生效，这里双重保险）
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 加载 ORM 模型 & Base
from app.database import Base  # noqa: E402
from app import models  # noqa: E402,F401  (side effect: 注册所有 ORM 类到 metadata)

# Alembic Config 对象，访问 alembic.ini 中的值
config = context.config

# -------------------- 数据库 URL 构造（与 app/database.py 保持一致） --------------------
_DB_PATH = os.environ.get("DB_PATH", "./timesheet.db")
_sqlalchemy_url = f"sqlite:///{_DB_PATH}"
config.set_main_option("sqlalchemy.url", _sqlalchemy_url)

# -------------------- Python 日志配置（如果 alembic.ini 中配置了 loggers） --------------------
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# autogenerate 用的元数据（核心！不能省略）
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    离线模式：直接把 DDL 输出为 SQL 字符串（不连接数据库）
    用法：alembic upgrade head --sql > schema.sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,   # SQLite 必需
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    在线模式：实际连接数据库并执行迁移（默认模式）
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,   # SQLite：对 ALTER TABLE 用 CREATE-COPY-DROP 模式兼容
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
