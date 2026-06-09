# 工时审核 API (Timesheet Review API)

基于 **Python 3.12 + FastAPI + SQLite** 的工时审核系统后端服务，已接入 Alembic 数据库迁移、Docker 多阶段构建与 GitHub Actions 持续集成。

## 功能概览

| 模块 | 功能说明 |
| ---- | -------- |
| 工时提交 | 员工提交工时记录（员工 ID、日期、小时数、项目标签），自动写入 SQLite |
| 主管审批 | 支持单条记录批准/拒绝，以及批量审批；所有操作写入审批历史记录表 |
| 异常工时标记 | 每日累计工时 > 12 小时，或工作日期为法定假日，自动打上 `anomaly` 标签，提供独立查询接口 |
| 数据库治理 | 基于 Alembic 的迁移方案，字段调整保留历史数据，不再使用 `create_all` |
| 生产部署 | 多阶段 Docker 镜像、健康检查、非 root 运行、持久化 Volume 挂载 |
| 持续集成 | GitHub Actions 串行执行 `ruff → pytest → docker build` 三阶段门禁 |

## 技术栈

- **Python 3.12**
- **FastAPI** 0.110
- **SQLAlchemy** 2.0 (ORM)
- **Alembic** 1.13 (Schema 迁移)
- **SQLite** (内置，无需额外安装)
- **Uvicorn** (ASGI 服务器)
- **pytest 8** + **httpx** (自动化测试，共 66 条用例)
- **ruff** (代码风格检查 / 格式化)

## 目录结构

```
21-timesheet-review-api/
├── .github/
│   └── workflows/ci.yml              # GitHub Actions 持续集成 (ruff → pytest → docker build)
├── app/
│   ├── __init__.py
│   ├── database.py                   # SQLAlchemy 引擎 + Alembic upgrade 封装
│   ├── models/                       # 数据库 ORM 模型
│   │   ├── user.py                   # User（员工 / 主管，自引用下属关系）
│   │   ├── timesheet.py              # 工时记录表
│   │   └── approval.py               # 审批记录 + 法定假日
│   ├── schemas/                      # Pydantic 请求/响应 Schema
│   ├── crud/                         # 数据库操作封装
│   └── routers/                      # 路由 (API 接口层)
├── tests/                            # pytest 测试套件 (66 cases)
│   ├── conftest.py
│   ├── test_anomaly_detection.py
│   ├── test_approvals.py
│   ├── test_holidays.py
│   └── test_deploy_assets.py         # 部署资产单测（Alembic / Dockerfile / compose）
├── migrations/
│   ├── env.py                        # Alembic 运行环境（SQLite render_as_batch 兼容）
│   ├── script.py.mako
│   └── versions/
│       └── 4e4d259e39e2_initial_schema_users_timesheets_.py
├── main.py                           # FastAPI 应用入口（lifespan 自动 alembic upgrade head）
├── seed.py                           # 最小化种子数据脚本
├── alembic.ini
├── requirements.txt                  # 含 alembic / pytest / httpx / ruff
├── ruff.toml                         # 代码风格配置 (line-length=120)
├── Dockerfile                        # 多阶段构建 (python:3.12-slim builder + runtime)
├── .dockerignore
├── docker-compose.yml                # 编排：服务 + 命名卷 + healthcheck
├── .env.example                      # 环境变量模板
└── README.md
```

## 快速开始

### 1. 环境准备 + 虚拟环境

```bash
# 克隆后在项目根目录执行
python3.12 -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. (可选) 配置环境变量

```bash
cp .env.example .env
# 根据需要修改 DB_PATH / PORT / LOG_LEVEL 等
```

> ⚠️ 见下文 **环境变量参考** 章节，每个变量的用途与合法取值均有说明。

### 4. (可选) 初始化种子数据

运行 `seed.py` 会先执行 `alembic upgrade head` 建表，再写入测试数据：

```bash
python seed.py
```

### 5. 启动服务

```bash
# 开发模式（代码变更自动重载）
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 生产模式（多 worker；服务启动时自动执行 alembic upgrade head）
DB_PATH=./timesheet.db \
  uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

启动后访问以下地址：

| 路径 | 说明 |
| ---- | ---- |
| `http://localhost:8000/`        | API 根信息 |
| `http://localhost:8000/health`  | **健康检查**（容器健康探针目标） |
| `http://localhost:8000/docs`    | **Swagger UI 交互式文档（推荐）** |
| `http://localhost:8000/redoc`   | ReDoc 文档 |

---

## 环境变量参考

所有可配置变量均在 `.env.example` 中提供模板。**部署时务必将 `.env.example` 复制为 `.env` 并根据环境调整**。

| 变量名 | 默认值 | 用途 | 合法取值 / 说明 |
| :----- | :----- | :--- | :-------------- |
| **`DB_PATH`** | `./timesheet.db` | SQLite 数据库文件路径 | — **开发 / 本地测试**：相对路径如 `./timesheet.db`<br>— **Docker / K8s**：必须落在挂载卷内，推荐 `/data/timesheet.db`<br>— **CI / 一次性脚本**：设为 `:memory:` 使用内存数据库（性能最佳，进程退出丢失） |
| **`HOST`** | `0.0.0.0` | uvicorn 绑定的 IP | 容器中**必须**为 `0.0.0.0`，否则宿主机无法访问；本地测试可使用 `127.0.0.1` |
| **`PORT`** | `8000` | uvicorn 监听的容器内端口 | `1 ~ 65535` 内整数，与 Dockerfile `EXPOSE` 保持一致，默认 `8000` |
| **`HOST_PORT`** | `8000` | docker-compose 宿主机映射端口 | 可覆盖默认 `8000`，如 `8080`，即 `HOST_PORT=8080 docker compose up` |
| **`WORKERS`** | `2` | uvicorn worker 进程数 | 建议值 = **CPU 核心数 × 2 + 1**；本地可以用 `1`，生产根据资源调整 |
| `APP_ENV` | `development` | 当前部署环境标签 | `development` · `staging` · `production`，仅用于日志/调试区分 |
| `DEBUG` | `false` | 开发模式调试开关 | `true` / `false`；生产必须保持 `false`，避免堆栈信息泄露 |
| `LOG_LEVEL` | `info` | 日志级别 | `debug` · `info` · `warning` · `error` · `critical`（小写） |
| `TZ` | `Asia/Shanghai` | 服务时区 | 标准 tz database 名称，如 `UTC`、`Asia/Tokyo`。**异常工时按自然日判断，时区设置错误会导致日期边界错误。** |
| `ANOMALY_HOURS_THRESHOLD` | `12` | 当日累计工时 anomaly 阈值 | 正整数，单位小时；超过该值自动标记 `anomaly`。可根据公司考勤制度调整（如 8/10/12） |
| `ANOMALY_ENABLE_HOLIDAY` | `true` | 法定假日报工是否自动 anomaly | `true` / `false`；设为 `false` 可在紧急运维期间暂时关闭假日异常规则 |
| `BUILDKIT_INLINE_CACHE` | `1` | Docker BuildKit 内联缓存开关 | 容器构建内部变量，一般无需修改 |
| `PYTHONDONTWRITEBYTECODE` | `1` | 禁止生成 `.pyc` 文件 | 容器与 CI 推荐开启；开发环境可关闭 |
| `PYTHONUNBUFFERED` | `1` | 禁用 stdout 缓冲 | 确保 Docker 日志与 uvicorn 输出实时可见 |

### 环境变量使用示例

```bash
# 例 1：生产环境（生产部署常用组合）
APP_ENV=production
DEBUG=false
DB_PATH=/data/timesheet.db
HOST=0.0.0.0
PORT=8000
WORKERS=4
LOG_LEVEL=warning
TZ=Asia/Shanghai
ANOMALY_HOURS_THRESHOLD=10

# 例 2：本地调试（带详细日志）
APP_ENV=development
DEBUG=true
DB_PATH=./timesheet.db
HOST=127.0.0.1
PORT=8000
WORKERS=1
LOG_LEVEL=debug
```

---

## 核心 API 速查

所有业务接口均挂载在 `/api/v1` 前缀下。

### 1. 工时提交接口

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| `POST` | `/api/v1/timesheets` | 提交一条工时记录（写入 DB 时自动 anomaly 检测） |
| `GET`  | `/api/v1/timesheets` | 分页查询工时列表，支持员工/日期/状态/项目过滤 |
| `GET`  | `/api/v1/timesheets/{id}` | 查询单条工时详情 |
| `PUT`  | `/api/v1/timesheets/{id}` | 修改工时（更新时会重新检测 anomaly） |
| `DELETE` | `/api/v1/timesheets/{id}` | 删除工时记录 |

**POST 示例 Body：**

```json
{
  "employee_id": 2,
  "date": "2026-06-10",
  "hours": 9,
  "project_tag": "PROJ-A",
  "description": "需求分析和方案评审"
}
```

### 2. 主管审批接口

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| `POST` | `/api/v1/approvals/single` | 单条审批（批准/拒绝） |
| `POST` | `/api/v1/approvals/bulk` | 批量审批，返回 processed/skipped/failed 分组统计 |
| `GET`  | `/api/v1/approvals/history/{timesheet_id}` | 查看某工时的审批历史 |
| `GET`  | `/api/v1/approvals/approver/{approver_id}` | 查看某主管的审批记录 |

**单条审批 Body：**

```json
{
  "timesheet_id": 1,
  "approver_id": 1,
  "action": "approved",
  "comment": "正常工时，批准。"
}
```

> `action` 取值：`approved` / `rejected`

**批量审批 Body：**

```json
{
  "timesheet_ids": [1, 2, 3],
  "approver_id": 1,
  "action": "rejected",
  "comment": "需要补充项目标签后重新提交。"
}
```

### 3. 异常工时标记 & 查询

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| `GET`    | `/api/v1/anomalies` | 查询所有打了 `anomaly` 标签的工时记录，支持员工/日期过滤 |
| `GET`    | `/api/v1/anomalies/holidays` | 查询已配置的法定假日列表 |
| `POST`   | `/api/v1/anomalies/holidays` | 新增法定假日（该日期的工时将自动标记 anomaly） |
| `DELETE` | `/api/v1/anomalies/holidays/{id}` | 删除法定假日配置 |

**自动 anomaly 判定规则**（在提交/更新工时记录时实时计算）：

1. 该员工当日累计工时 **> `ANOMALY_HOURS_THRESHOLD`（默认 12 小时）** → 标记 `anomaly`
2. 工作日期 **命中法定假日表**，且 `ANOMALY_ENABLE_HOLIDAY=true` → 标记 `anomaly`

---

## 数据模型

| 表名 | 关键字段 | 用途 |
| ---- | -------- | ---- |
| `users` | `employee_id`, `name`, `email`, `role(employee/supervisor/admin)`, `supervisor_id` | 用户表（自关联主管-下属关系） |
| `timesheets` | `employee_id`, `date`, `hours`, `project_tag`, `status(pending/approved/rejected)`, `tags` | 工时记录表，`tags` 中包含 `anomaly` |
| `approval_records` | `timesheet_id`, `approver_id`, `action`, `comment`, `created_at` | 审批历史（不可变审计记录） |
| `holidays` | `date`, `name` | 法定假日配置表 |
| `alembic_version` | `version_num` | 系统内部：记录当前 schema 版本号 |

---

## 数据库迁移（Alembic）

本项目已**完全移除** `Base.metadata.create_all`，表结构由 Alembic 统一治理，服务启动时自动执行 `alembic upgrade head`。

### 常用命令

```bash
# 查看当前数据库版本
alembic current

# 升级到最新版（服务启动已自动执行）
alembic upgrade head

# 回滚上一个版本
alembic downgrade -1

# 回滚到最开始的空库
alembic downgrade base

# 查看迁移历史
alembic history --verbose

# 根据模型变更自动生成新版本（字段调整时使用）
alembic revision --autogenerate -m "add_xxx_field_to_timesheets"

# 预览 SQL（不实际执行，生产变更前强烈建议）
alembic upgrade head --sql > /tmp/schema.sql
```

> **SQLite 兼容**：`migrations/env.py` 已启用 `render_as_batch=True`，字段增删时会自动走 **CREATE-COPY-DROP** 路径，兼容 SQLite 原生不支持 `ALTER TABLE` 的限制。

### 新增一个字段的完整流程

```bash
# 1) 编辑 app/models/xxx.py 修改 ORM 模型
# 2) 生成迁移脚本
alembic revision --autogenerate -m "add_new_field"
# 3) 检查 migrations/versions/<新文件>.py 内容是否正确
# 4) 应用到本地数据库
alembic upgrade head
# 5) 启动服务验证
```

---

## 代码质量（ruff）

使用 **ruff** 进行代码风格检查与自动修复（替代 flake8 + isort + black）。

```bash
# 风格检查（CI 会强制执行，失败阻塞合并）
ruff check .

# 自动修复能修的问题（导入排序、未使用变量等）
ruff check --fix .

# 格式化代码（可选项，CI 中仅做 --check）
ruff format .

# 检查格式化差异（不修改文件，CI 门禁）
ruff format --check --diff .
```

详见 `ruff.toml`：`line-length=120`，忽略 UP007/UP035（允许 typing 导入两种风格）、E501（行长度不阻塞）。

---

## 测试（pytest）

测试套件覆盖 anomaly 自动检测、单条/批量审批、假日 CRUD，以及部署资产（Alembic CLI / Dockerfile / docker-compose）。

```bash
# 运行全部 66 条用例
pytest tests/ -v

# 仅跑核心业务用例（不含部署资产）
pytest tests/ -v --ignore=tests/test_deploy_assets.py

# 带覆盖率报告（需额外安装 pytest-cov）
pytest tests/ -v --cov=app --cov=main
```

CI 中测试期 `DB_PATH=:memory:`，确保测试之间完全独立，不访问真实数据库文件。

---

## 容器化部署

### 快速启动（docker compose）

```bash
# 构建镜像 + 后台启动（含 SQLite 持久化卷）
docker compose up -d --build

# 查看服务 / 健康状态
docker compose ps
curl http://localhost:8000/health

# 停止服务（保留数据卷）
docker compose down

# ⚠️ 彻底清除数据库卷（数据会丢失）
docker compose down -v
```

### 镜像特性

- 多阶段构建：`builder` 阶段安装编译依赖，`runtime` 阶段仅保留运行时文件
- 运行用户：**非 root** 的 `appuser`（UID 10001，符合 Kubernetes 安全最佳实践）
- **健康检查**：每 30s 探测 `/health` 端点，5s 超时，失败 3 次后容器自动重启
- **持久化**：`VOLUME ["/data"]`，配合 docker-compose 命名卷 `timesheet-data` 防止 `docker compose down` 丢数据
- **启动顺序**：`CMD` 先执行 `alembic upgrade head` 迁移，再 `uvicorn main:app`，保证新版本上线先升级 schema

### 手动构建镜像

```bash
docker build -t timesheet-review-api:latest .
docker run -d \
  --name timesheet-api \
  -p 8000:8000 \
  -v timesheet-data:/data \
  -e TZ=Asia/Shanghai \
  timesheet-review-api:latest
```

---

## 持续集成（GitHub Actions）

工作流文件：`.github/workflows/ci.yml`

**触发条件**：
- `push` 到 `main / master / develop`（忽略纯 Markdown 变更）
- `pull_request` 新建 / 更新 / 重开

**执行顺序（串行，前一步失败则后续全部终止）**：

| 阶段 | Job 名称 | 说明 |
| :--- | :------- | :--- |
| ① | **Ruff Lint & Style** | Python 3.12 矩阵，先 `ruff check .` 再 `ruff format --check`；任何规则违规均阻止合并 |
| ② | **Pytest Unit Tests** | 依赖 ① 成功；Python 3.12，`DB_PATH=:memory:`，运行 `tests/` 全部 66 条用例，失败时上传 `*.db` 调试产物 |
| ③ | **Docker Image Build** | 依赖 ② 成功；使用 buildx 层缓存，构建 immutable 镜像 `timesheet-review-api:ci-<sha>`；额外校验镜像体积 ≤ 250 MB |

**CI 本地复现（手动）**：

```bash
ruff check .
ruff format --check --diff .
DB_PATH=:memory: pytest tests/ -v --tb=short
docker build -t timesheet-review-api:local .
```

---

## 常见操作

### 重新生成数据库

由于使用 Alembic 迁移，推荐用官方迁移命令而非直接删库：

```bash
# 方案 A：干净回滚（保留迁移记录体系）
alembic downgrade base      # 清空所有表
alembic upgrade head        # 重新建到最新版
python seed.py              # （可选）重新插入种子数据

# 方案 B：粗暴重置（仅开发环境）
rm timesheet.db && python seed.py
```

### 升级生产环境的字段

```bash
# 1. 本地完成模型修改 + 生成 revision
alembic revision --autogenerate -m "add department to users"

# 2. 手动检查 migrations/versions/ 生成的文件（Alembic 自动生成偶尔漏索引）

# 3. 本地 pytest 全量跑一遍
pytest tests/ -v

# 4. 合入主干；CI 通过后部署（容器启动会自动 alembic upgrade head）
```

### 健康检查脚本（运维）

```bash
#!/usr/bin/env bash
# 用于容器 / K8s livenessProbe
if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "✅ service healthy"
  exit 0
else
  echo "❌ service unhealthy"
  exit 1
fi
```

---

## License

内部项目，无开源许可。
