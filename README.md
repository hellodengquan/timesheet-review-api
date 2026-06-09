# 工时审核 API (Timesheet Review API)

基于 **Python + FastAPI + SQLite** 的工时审核系统后端服务。

## 功能概览

| 模块 | 功能说明 |
| ---- | -------- |
| 工时提交 | 员工提交工时记录（员工 ID、日期、小时数、项目标签），自动写入 SQLite |
| 主管审批 | 支持单条记录批准/拒绝，以及批量审批；所有操作写入审批历史记录表 |
| 异常工时标记 | 每日累计工时 > 12 小时，或工作日期为法定假日，自动打上 `anomaly` 标签，提供独立查询接口 |

## 技术栈

- **Python 3.10+**
- **FastAPI** 0.110
- **SQLAlchemy** 2.0 (ORM)
- **SQLite** (内置，无需额外安装)
- **Uvicorn** (ASGI 服务器)

## 目录结构

```
21-timesheet-review-api/
├── app/
│   ├── __init__.py
│   ├── database.py             # SQLAlchemy 引擎 & 会话工厂
│   ├── models/                 # 数据库 ORM 模型
│   │   ├── __init__.py
│   │   ├── user.py             # User（员工 / 主管）
│   │   ├── timesheet.py        # 工时记录表
│   │   └── approval.py         # 审批记录 & 法定假日
│   ├── schemas/                # Pydantic 请求/响应 Schema
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── timesheet.py
│   │   └── approval.py
│   ├── crud/                   # 数据库操作封装
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── timesheet.py
│   │   └── approval.py
│   └── routers/                # 路由 (API 接口层)
│       ├── __init__.py
│       ├── users.py
│       ├── timesheets.py       # 工时提交接口
│       ├── approvals.py        # 主管审批接口（单条/批量）
│       └── anomalies.py        # 异常工时 & 假日接口
├── main.py                     # FastAPI 应用入口
├── seed.py                     # 最小化种子数据脚本
├── requirements.txt
└── README.md
```

## 快速开始

### 1. 环境准备

推荐使用虚拟环境：

```bash
# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境 (macOS / Linux)
source .venv/bin/activate

# 激活虚拟环境 (Windows PowerShell)
# .venv\Scripts\Activate.ps1
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. (可选) 初始化种子数据

运行 `seed.py` 快速创建测试用户、法定假日和样例工时记录：

```bash
python seed.py
```

> 运行后会在项目根目录自动生成 `timesheet.db` (SQLite 数据库文件)。

### 4. 启动服务

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

启动后访问以下地址：

| 路径 | 说明 |
| ---- | ---- |
| `http://localhost:8000/` | API 根信息 |
| `http://localhost:8000/health` | 健康检查 |
| `http://localhost:8000/docs` | **Swagger UI 交互式文档（推荐）** |
| `http://localhost:8000/redoc` | ReDoc 文档 |

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

1. 该员工当日累计工时 **超过 12 小时** → 标记 `anomaly`
2. 工作日期 **命中法定假日表** → 标记 `anomaly`

## 数据模型简述

| 表名 | 关键字段 | 用途 |
| ---- | -------- | ---- |
| `users` | `employee_id`, `name`, `email`, `role(employee/supervisor/admin)`, `supervisor_id` | 用户（自关联主管下属关系） |
| `timesheets` | `employee_id`, `date`, `hours`, `project_tag`, `status(pending/approved/rejected)`, `tags` | 工时记录，`tags` 中包含 `anomaly` |
| `approval_records` | `timesheet_id`, `approver_id`, `action`, `comment`, `created_at` | 审批历史（不可变的审计记录） |
| `holidays` | `date`, `name` | 法定假日配置表 |

## 常见操作

### 重新生成数据库

由于使用 SQLite，只需删除根目录下的 `timesheet.db`，然后启动服务或再次运行 `seed.py`，表结构会自动重新创建。

### 运行测试 (可选扩展)

如需添加测试脚本，推荐使用 `pytest + httpx`，可配置测试时使用独立的 `test.db`。

---

**提示**：推荐先使用 Swagger UI (`/docs`) 快速体验所有接口。
