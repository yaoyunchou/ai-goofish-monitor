"""
登录状态管理路由（DB + 文件双写）
"""
import os
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.services.account_state_store import save_account_state, delete_account_state


router = APIRouter(prefix="/api/login-state", tags=["login-state"])


class LoginStateUpdate(BaseModel):
    """登录状态更新模型"""
    content: str


@router.post("", response_model=dict)
async def update_login_state(
    data: LoginStateUpdate,
):
    """接收前端发送的登录状态JSON字符串，保存到 DB + xianyu_state.json"""
    state_file = "xianyu_state.json"

    try:
        content = json.loads(data.content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="提供的内容不是有效的JSON格式。")

    try:
        save_account_state("default", content, write_file=True)
        # 兼容旧代码：同时写 xianyu_state.json
        with open(state_file, 'w', encoding='utf-8') as f:
            f.write(data.content)
        return {"message": f"登录状态已保存到数据库和文件 '{state_file}'。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存登录状态时出错: {e}")


@router.delete("", response_model=dict)
async def delete_login_state():
    """删除登录状态（DB + 文件）"""
    state_file = "xianyu_state.json"
    delete_account_state("default")
    if os.path.exists(state_file):
        os.remove(state_file)
    return {"message": "登录状态已删除。"}
