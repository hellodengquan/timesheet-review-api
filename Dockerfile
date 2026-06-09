# ============================================================
#  Stage 1 : Builder — 安装编译依赖，构建虚拟环境
# ============================================================
FROM python:3.12-slim AS builder

# 防止 Python 写入 .pyc 文件 / 启用无缓冲 stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# 安装编译依赖（例如 cryptography 等包需要）
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential gcc \
 && rm -rf /var/lib/apt/lists/*

# 创建独立虚拟环境并安装依赖
RUN python -m venv ${VIRTUAL_ENV}
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ============================================================
#  Stage 2 : Runtime — 仅拷贝必要产物，体积极小
# ============================================================
FROM python:3.12-slim AS runtime

LABEL maintainer="timesheet-review-api" \
      description="Timesheet Review API (FastAPI + SQLite + Alembic)"

# 生产环境变量（可由 k8s env 覆盖）
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    APP_HOME=/app \
    PORT=8000 \
    WORKERS=2 \
    DB_PATH=/data/timesheet.db

# 运行时仅需 ca-certificates，避免 apt 缓存残留
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户与数据目录（挂载 volume 用）
RUN groupadd --system appuser \
 && useradd  --system --gid appuser --home-dir ${APP_HOME} --shell /sbin/nologin appuser \
 && mkdir -p ${APP_HOME} /data \
 && chown -R appuser:appuser ${APP_HOME} /data

# 从 builder 拷贝整个虚拟环境（已包含全部依赖）
COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# 拷贝应用源码
WORKDIR ${APP_HOME}
COPY --chown=appuser:appuser . .

# 暴露 FastAPI 默认端口（k8s 部署时必须通过 EXPOSE 声明）
EXPOSE 8000

# SQLite 数据库文件存放目录（Docker Compose / k8s 可挂载卷）
VOLUME ["/data"]

# 切换到非 root 用户（生产安全要求）
USER appuser

# 健康检查：命中 FastAPI /health 端点
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl --fail http://127.0.0.1:${PORT}/health || exit 1

# 默认启动命令：先执行 alembic 迁移，再启动 uvicorn
# 迁移成功后再启动服务；避免旧库结构导致 API 报错
CMD alembic upgrade head \
 && uvicorn main:app \
    --host 0.0.0.0 \
    --port ${PORT} \
    --workers ${WORKERS} \
    --proxy-headers \
    --forwarded-allow-ips="*"
