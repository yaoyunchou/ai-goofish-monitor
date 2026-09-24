"""
新架构的主应用入口
整合所有路由和服务
"""
import asyncio
import logging
import logging.config
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.infrastructure.logging_config import UVICORN_LOG_CONFIG, configure_app_logging

configure_app_logging()
app_logger = logging.getLogger("app")

from src.api.routes import (
    dashboard,
    tasks,
    logs,
    settings,
    prompts,
    results,
    login_state,
    websocket,
    accounts,
    collections,
    seller_subscriptions,
    shop_analytics,
    xhs,
)
from src.api.dependencies import (
    set_process_service,
    set_scheduler_service,
    set_task_generation_service,
)
from src.domain.seller_subscription import SELLER_SUBSCRIPTION_JOB_ID
from src.services.seller_subscription_service import migrate_legacy_subscription_tasks
from src.services.seller_subscription_storage import get_schedule, set_subscription_running
from src.services.xhs_storage import get_schedule as get_xhs_schedule
from src.services.xhs_note_storage import get_schedule as get_xhs_note_schedule
from src.services.task_service import TaskService
from src.services.process_service import ProcessService
from src.services.scheduler_service import SchedulerService
from src.services.task_log_cleanup_service import cleanup_task_logs
from src.services.task_generation_service import TaskGenerationService
from src.infrastructure.persistence.storage_bootstrap import bootstrap_storage
from src.infrastructure.persistence.task_repository_factory import create_task_repository
from src.infrastructure.config.settings import settings as app_settings


# 全局服务实例
process_service = ProcessService()
scheduler_service = SchedulerService(process_service)
task_generation_service = TaskGenerationService()


async def _sync_task_runtime_status(task_id: int, is_running: bool) -> None:
    if task_id == SELLER_SUBSCRIPTION_JOB_ID:
        await set_subscription_running(is_running)
        await websocket.broadcast_message(
            "seller_subscription_status_changed",
            {"is_running": is_running},
        )
        return

    task_service = TaskService(create_task_repository())
    task = await task_service.get_task(task_id)
    if not task or task.is_running == is_running:
        return
    await task_service.update_task_status(task_id, is_running)
    await websocket.broadcast_message(
        "task_status_changed",
        {"id": task_id, "is_running": is_running},
    )


process_service.set_lifecycle_hooks(
    on_started=lambda task_id: _sync_task_runtime_status(task_id, True),
    on_stopped=lambda task_id: _sync_task_runtime_status(task_id, False),
)

# 设置全局 ProcessService 实例供依赖注入使用
set_process_service(process_service)
set_scheduler_service(scheduler_service)
set_task_generation_service(task_generation_service)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时：debugpy 下 stdout 会被 detach，重新绑定 uvicorn 日志到 stderr
    logging.config.dictConfig(UVICORN_LOG_CONFIG)
    configure_app_logging()
    print("正在启动应用...")
    from src.services.channel_workers import get_channel_workers

    get_channel_workers().bind(asyncio.get_running_loop())
    bootstrap_storage()
    cleanup_task_logs(keep_days=app_settings.task_log_retention_days)

    # 重置所有任务状态为停止
    task_repo = create_task_repository()
    task_service = TaskService(task_repo)
    tasks_list = await task_service.get_all_tasks()

    for task in tasks_list:
        if task.is_running:
            await task_service.update_task_status(task.id, False)

    migrated = await migrate_legacy_subscription_tasks()
    if migrated:
        print(f"已从旧版订阅任务迁移 {migrated} 个卖家")

    await set_subscription_running(False)
    schedule = await get_schedule()
    await scheduler_service.reload_seller_subscription_job(schedule)
    scheduler_service.reload_monitor_health_job()
    xhs_schedule = get_xhs_schedule()
    await scheduler_service.reload_xhs_job(xhs_schedule)
    await scheduler_service.reload_xhs_note_job(get_xhs_note_schedule())
    await scheduler_service.reload_jobs(tasks_list)
    scheduler_service.start()

    print("应用启动完成")

    yield

    # 关闭时
    print("正在关闭应用...")
    scheduler_service.stop()
    await process_service.stop_all()
    print("应用已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="闲鱼智能监控机器人",
    description="基于AI的闲鱼商品监控系统",
    version="2.0.0",
    lifespan=lifespan
)


def _log_api_error(message: str) -> None:
    """debugpy 下 logging.StreamHandler 可能失败，直接写 stderr 更稳。"""
    try:
        sys.stderr.write(message + "\n")
        sys.stderr.flush()
    except Exception:
        pass


@app.exception_handler(HTTPException)
async def log_http_exception(request: Request, exc: HTTPException):
    """在终端一行输出 API 业务错误（404 等），不打印整段 traceback。"""
    if exc.status_code >= 400:
        _log_api_error(
            f"WARNING app: {request.method} {request.url.path} -> {exc.status_code}: {exc.detail}"
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

# 注册路由
app.include_router(tasks.router)
app.include_router(dashboard.router)
app.include_router(logs.router)
app.include_router(settings.router)
app.include_router(prompts.router)
app.include_router(results.router)
app.include_router(collections.router)
app.include_router(login_state.router)
app.include_router(websocket.router)
app.include_router(accounts.router)
app.include_router(seller_subscriptions.router)
app.include_router(shop_analytics.router)
app.include_router(xhs.router)
from src.api.routes import xhs_notes
app.include_router(xhs_notes.router)

# 挂载静态文件
# 旧的静态文件目录（用于截图等）
app.mount("/static", StaticFiles(directory="static"), name="static")

# 挂载 Vue 3 前端构建产物
# 注意：需要在所有 API 路由之后挂载，以避免覆盖 API 路由
import os
if os.path.exists("dist"):
    app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")


# 健康检查端点
@app.get("/health")
async def health_check():
    """健康检查（无需认证）"""
    return {"status": "healthy", "message": "服务正常运行"}


# 认证状态检查端点
from fastapi.responses import FileResponse
from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/auth/status")
async def auth_status(payload: LoginRequest):
    """检查认证状态"""
    if payload.username == app_settings.web_username and payload.password == app_settings.web_password:
        return {"authenticated": True, "username": payload.username}
    raise HTTPException(status_code=401, detail="认证失败")


# 主页路由 - 服务 Vue 3 SPA
@app.get("/")
async def read_root(request: Request):
    """提供 Vue 3 SPA 的主页面"""
    if os.path.exists("dist/index.html"):
        return FileResponse("dist/index.html")
    else:
        return JSONResponse(
            status_code=500,
            content={"error": "前端构建产物不存在，请先运行 cd web-ui && npm run build"}
        )


# Catch-all 路由 - 处理所有前端路由（必须放在最后）
@app.get("/{full_path:path}")
async def serve_spa(request: Request, full_path: str):
    """
    Catch-all 路由，将所有非 API 请求重定向到 index.html
    这样可以支持 Vue Router 的 HTML5 History 模式
    """
    # 未匹配的 /api/* 必须返回 JSON，避免前端/curl 误拿到 index.html
    if full_path == "api" or full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail=f"API 路由未找到: /{full_path}")

    # 如果请求的是静态资源（如 favicon.ico），返回 404
    if full_path.endswith(('.ico', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.css', '.js', '.json')):
        return JSONResponse(status_code=404, content={"error": "资源未找到"})

    # 其他所有路径都返回 index.html，让前端路由处理
    if os.path.exists("dist/index.html"):
        return FileResponse("dist/index.html")
    else:
        return JSONResponse(
            status_code=500,
            content={"error": "前端构建产物不存在，请先运行 cd web-ui && npm run build"}
        )


if __name__ == "__main__":
    import uvicorn
    from src.infrastructure.config.settings import settings

    print(f"启动新架构应用，端口: {app_settings.server_port}")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=app_settings.server_port,
        log_config=UVICORN_LOG_CONFIG,
    )
