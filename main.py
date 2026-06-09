from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.database import run_alembic_upgrade_head
from app.routers import users, timesheets, approvals, anomalies


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 服务启动前执行 Alembic 迁移，保证表结构与代码版本一致
    run_alembic_upgrade_head("head")
    yield


app = FastAPI(
    title="工时审核 API (Timesheet Review API)",
    description=(
        "基于 FastAPI 和 SQLite 的工时审核系统。\n\n"
        "核心功能：\n"
        "- 工时提交（员工 ID、日期、小时数、项目标签）\n"
        "- 主管审批（单条 / 批量批准或拒绝，保存审批历史）\n"
        "- 异常工时标记（每日累计 > 12 小时 或 法定假日自动标记 anomaly）"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(users.router, prefix="/api/v1")
app.include_router(timesheets.router, prefix="/api/v1")
app.include_router(approvals.router, prefix="/api/v1")
app.include_router(anomalies.router, prefix="/api/v1")


@app.get("/", tags=["root"])
def root():
    return {
        "name": "工时审核 API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health", tags=["root"])
def health_check():
    return {"status": "ok"}
