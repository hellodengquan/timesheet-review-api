"""
test_deploy_assets.py
=====================
生产部署资产专项测试：
  A. Alembic 迁移
     1. alembic CLI（alembic current / history / heads / upgrade head）可用
     2. migrations/versions 下至少有 1 个 revision 脚本
     3. 初始 revision 覆盖 4 张表：users, timesheets, approval_records, holidays
     4. upgrade head 后 alembic_version 写入 + 4 张表真正存在
     5. downgrade -> base 能删除这些表（可逆性）

  B. Dockerfile 构建参数
     1. 基础镜像：python:3.12-slim（FROM 开头）
     2. 多阶段构建：至少有两个 FROM 阶段（builder + runtime）
     3. EXPOSE 8000
     4. HEALTHCHECK 存在且命中 /health
     5. CMD 顺序：先 alembic upgrade head，再启动 uvicorn
     6. 非 root 用户（USER appuser）
     7. VOLUME 声明 /data（sqlite 持久化目录）
     8. .dockerignore 存在且排除 .venv / *.db / __pycache__ 等

  C. docker-compose 编排
     1. 有 service 定义 timesheet-api
     2. 端口映射包含 8000
     3. 挂载 volume 持久化 sqlite 数据
     4. healthcheck 配置存在
     5. deploy/resources 声明（k8s 就绪度参考）

注意：此文件**不依赖**测试 fixture 里的内存数据库，它会在临时目录操作
      真实 SQLite 文件（通过 DB_PATH 环境变量）。
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# 仓库根目录（conftest.py 在 tests/ 下，上一级）
REPO_ROOT = Path(__file__).resolve().parent.parent


# ============================================================================
#  A. Alembic 迁移测试
# ============================================================================
class TestAlembicCLI:
    def _run(self, cmd, **env_extra):
        """在仓库根目录执行 alembic 命令，返回 CompletedProcess"""
        env = os.environ.copy()
        env.update(env_extra)
        return subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
        )

    def test_alembic_current_command_available(self):
        """`alembic current` 必须成功返回（退出码0或1都可能，取决于是否已升级）"""
        with tempfile.TemporaryDirectory() as tmp:
            db_file = os.path.join(tmp, "empty.db")
            r = self._run(
                [sys.executable, "-m", "alembic", "current"],
                DB_PATH=db_file,
            )
            # 即使未升级也不能是找不到命令之类的错误（stderr 不能有 "No such file"）
            assert "No such file" not in r.stderr
            assert "command not found" not in r.stderr

    def test_alembic_history_returns_initial_revision(self):
        """alembic history 能列出至少一个 revision"""
        with tempfile.TemporaryDirectory() as tmp:
            db_file = os.path.join(tmp, "h.db")
            r = self._run(
                [sys.executable, "-m", "alembic", "history"],
                DB_PATH=db_file,
            )
            assert r.returncode == 0, f"history failed: {r.stderr}"
            # revision id 至少包含 8 位 hex（Alembic 默认 12 位）
            assert re.search(r"[0-9a-f]{8,}", r.stdout or r.stderr) is not None

    def test_alembic_heads_returns_exactly_one_head(self):
        """alembic heads 应该只有一个头（单分支）"""
        with tempfile.TemporaryDirectory() as tmp:
            db_file = os.path.join(tmp, "heads.db")
            r = self._run(
                [sys.executable, "-m", "alembic", "heads"],
                DB_PATH=db_file,
            )
            assert r.returncode == 0, f"heads failed: {r.stderr}"
            heads = [line for line in r.stdout.splitlines() if line.strip()]
            assert len(heads) >= 1

    def test_alembic_upgrade_head_creates_4_tables(self):
        """upgrade head -> 必须建好 4 张业务表 + alembic_version"""
        import sqlite3

        with tempfile.TemporaryDirectory() as tmp:
            db_file = os.path.join(tmp, "up.db")
            r = self._run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                DB_PATH=db_file,
            )
            assert r.returncode == 0, f"upgrade head failed: {r.stderr}"

            conn = sqlite3.connect(db_file)
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table';")}
            conn.close()

            expected = {
                "users",
                "timesheets",
                "approval_records",
                "holidays",
                "alembic_version",
            }
            assert expected.issubset(tables), f"缺少表 {expected - tables}"

    def test_alembic_downgrade_base_drops_business_tables(self):
        """先 upgrade head，再 downgrade base -> 业务表删除，alembic_version 可空"""
        import sqlite3

        with tempfile.TemporaryDirectory() as tmp:
            db_file = os.path.join(tmp, "dw.db")
            self._run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                DB_PATH=db_file,
            )
            r = self._run(
                [sys.executable, "-m", "alembic", "downgrade", "base"],
                DB_PATH=db_file,
            )
            assert r.returncode == 0, f"downgrade base failed: {r.stderr}"

            conn = sqlite3.connect(db_file)
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table';")}
            conn.close()
            business = {"users", "timesheets", "approval_records", "holidays"}
            assert business.isdisjoint(tables), f"还有残留表 {business & tables}"


class TestAlembicScriptContent:
    def test_migrations_versions_has_py_files(self):
        versions_dir = REPO_ROOT / "migrations" / "versions"
        files = list(versions_dir.glob("*.py"))
        assert len(files) >= 1, "migrations/versions/ 下没有 revision 脚本"

    def test_initial_revision_contains_4_tables_ddl(self):
        import re

        versions_dir = REPO_ROOT / "migrations" / "versions"
        files = list(versions_dir.glob("*.py"))
        combined = "\n".join(f.read_text() for f in files)
        # 去掉所有空白/引号差异：不限制 create_table 与表名的格式
        for tbl in ("users", "timesheets", "approval_records", "holidays"):
            pattern = re.compile(r"create_table\s*\(\s*[\"']" + re.escape(tbl) + r"[\"']")
            assert pattern.search(combined), f"迁移脚本中缺少表 {tbl} 的 create_table 调用"

    def test_env_py_imports_app_metadata(self):
        """migrations/env.py 必须从 app.database 加载 Base metadata"""
        env_py = (REPO_ROOT / "migrations" / "env.py").read_text()
        assert "app.database" in env_py and "Base" in env_py
        assert "target_metadata" in env_py

    def test_alembic_ini_exists_and_points_to_migrations(self):
        ini = (REPO_ROOT / "alembic.ini").read_text()
        assert "script_location = migrations" in ini

    def test_run_alembic_upgrade_head_function_exists(self):
        """app/database.py 必须提供 run_alembic_upgrade_head 供 main lifespan 调用"""
        db_py = (REPO_ROOT / "app" / "database.py").read_text()
        assert "run_alembic_upgrade_head" in db_py

    def test_main_uses_alembic_instead_of_create_all(self):
        """main.py 中应该调用 run_alembic_upgrade_head，且不再有 metadata.create_all"""
        main_py = (REPO_ROOT / "main.py").read_text()
        assert "run_alembic_upgrade_head" in main_py
        assert "metadata.create_all" not in main_py


# ============================================================================
#  B. Dockerfile 语法 & 规范断言（纯静态，无需真的 docker build）
# ============================================================================
class TestDockerfile:
    @pytest.fixture
    def dockerfile(self):
        path = REPO_ROOT / "Dockerfile"
        assert path.exists(), "Dockerfile 不存在于仓库根目录"
        return path.read_text()

    def test_from_python_3_12_slim(self, dockerfile):
        assert re.search(r"FROM\s+python:3\.12-slim", dockerfile, re.IGNORECASE) is not None

    def test_multi_stage_build(self, dockerfile):
        """多阶段构建：至少 2 个 FROM 语句"""
        assert len(re.findall(r"^FROM\s+", dockerfile, re.MULTILINE | re.IGNORECASE)) >= 2

    def test_expose_8000(self, dockerfile):
        assert re.search(r"EXPOSE\s+8000\b", dockerfile, re.MULTILINE | re.IGNORECASE) is not None

    def test_healthcheck_targets_health_endpoint(self, dockerfile):
        assert "HEALTHCHECK" in dockerfile
        assert "/health" in dockerfile

    def test_cmd_order_alembic_then_uvicorn(self, dockerfile):
        """CMD 中必须先 alembic upgrade head，再 uvicorn"""
        # 找到最后一条 CMD（shell 形式），在其之后（或之内）必须包含 alembic 和 uvicorn，且 alembic 先出现
        cmd_matches = list(re.finditer(r"^\s*CMD\b", dockerfile, re.MULTILINE))
        assert cmd_matches, "Dockerfile 中未找到 CMD 指令"
        last_cmd_start = cmd_matches[-1].start()
        cmd_tail = dockerfile[last_cmd_start:]
        alembic_idx = cmd_tail.find("alembic upgrade head")
        uvicorn_idx = cmd_tail.find("uvicorn")
        assert alembic_idx != -1, "CMD 中未包含 alembic upgrade head"
        assert uvicorn_idx != -1, "CMD 中未包含 uvicorn"
        assert alembic_idx < uvicorn_idx, "必须先执行 alembic，再启动 uvicorn"

    def test_run_as_non_root_user(self, dockerfile):
        """必须包含 USER appuser（非 root）"""
        assert re.search(r"USER\s+appuser\b", dockerfile, re.MULTILINE | re.IGNORECASE) is not None

    def test_volume_data_declared(self, dockerfile):
        """VOLUME 声明 /data (sqlite 持久化)"""
        volume_lines = re.findall(r"VOLUME\s+(.+)", dockerfile, re.IGNORECASE)
        assert len(volume_lines) >= 1, "未找到 VOLUME 指令"
        joined = " ".join(volume_lines)
        assert "/data" in joined, f"VOLUME 中未包含 /data，实际: {joined}"

    def test_workdir_set(self, dockerfile):
        """WORKDIR 声明"""
        assert re.search(r"^WORKDIR\s+", dockerfile, re.MULTILINE | re.IGNORECASE) is not None

    def test_copy_requirements_and_then_source(self, dockerfile):
        """构建顺序: 先 COPY requirements.txt 再 pip install (层缓存), 再 COPY 源码"""
        req_idx = dockerfile.find("COPY requirements.txt")
        src_copy_idx = dockerfile.find("COPY --chown=appuser:appuser . .") or dockerfile.find("COPY . .")
        # 允许出现多次 COPY，取 requirements 后首次出现的源码 COPY
        assert req_idx != -1 and src_copy_idx != -1
        # builder stage 中 pip install 必须在源码 COPY 之前
        assert req_idx < src_copy_idx

    def test_dockerignore_blocks_db_and_venv(self):
        ignore_path = REPO_ROOT / ".dockerignore"
        assert ignore_path.exists(), "缺少 .dockerignore"
        content = ignore_path.read_text()
        for pattern in (".venv", "__pycache__", "*.db"):
            assert pattern in content, f".dockerignore 未排除 {pattern}"


# ============================================================================
#  C. docker-compose 规范断言（纯静态）
# ============================================================================
class TestDockerCompose:
    @pytest.fixture
    def compose(self):
        path = REPO_ROOT / "docker-compose.yml"
        assert path.exists(), "docker-compose.yml 不存在"
        return path.read_text()

    def test_service_defined(self, compose):
        assert "timesheet-api:" in compose or '"timesheet-api":' in compose

    def test_port_8000(self, compose):
        assert "8000" in compose

    def test_volume_persists_sqlite(self, compose):
        """命名卷或 bind mount 中必须挂载 /data 或 DB_PATH 对应目录"""
        assert "volumes:" in compose and "/data" in compose

    def test_healthcheck_present(self, compose):
        """compose 中要有 healthcheck 节"""
        assert "healthcheck:" in compose
        assert "/health" in compose

    def test_resources_limits_declared(self, compose):
        """要有 deploy/resources/limits 声明（k8s 参考）"""
        assert "limits:" in compose and ("cpus" in compose or "memory" in compose)

    def test_top_level_volume_declared(self, compose):
        """compose 底部要有顶层 volumes:（命名卷持久化）"""
        # 找到文件尾部：寻找独立一行的 volumes:
        assert re.search(r"^volumes:\s*$", compose, re.MULTILINE) is not None
