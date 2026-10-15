"""统一响应与鉴权装饰器。"""

from functools import wraps
from typing import Any

from flask import g, jsonify, request
from sqlmodel import Session

from ..database import engine
from ..models import User
from ..services import site_config
from ..services import user_session as session_service


def ok(data: Any = None, msg: str = "success"):
    return jsonify({"code": 0, "msg": msg, "data": data})


def fail(msg: str = "请求失败", http_status: int = 400, code: int = 1, data: Any = None):
    return jsonify({"code": code, "msg": msg, "data": data}), http_status


def get_json() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


# ---------------- Cookie 会话（需求 10：cookie 存储登录信息，不采用令牌校验） ----------------

def set_session_cookie(response, token: str) -> None:
    """下发登录 Cookie：HttpOnly 防 XSS 窃取，有效期 = 会话空闲时长。"""
    response.set_cookie(
        session_service.COOKIE_NAME,
        token,
        max_age=site_config.session_idle_minutes() * 60,
        httponly=True,
        samesite="Lax",
        path="/",
    )


def clear_session_cookie(response) -> None:
    response.delete_cookie(session_service.COOKIE_NAME, path="/")


def current_session_token() -> str:
    return request.cookies.get(session_service.COOKIE_NAME, "")


def current_user_id() -> int | None:
    """从 Cookie 会话解析当前用户 ID；未登录或会话过期返回 None。"""
    token = current_session_token()
    if not token:
        return None
    with Session(engine) as session:
        record = session_service.get_valid_session(session, token)
        return record.user_id if record is not None else None


def require_auth(admin: bool = False):
    """Cookie 会话鉴权：注入数据库会话与当前用户到 flask.g；admin=True 时额外要求管理员。

    空闲超过站点配置 session_idle_minutes 未活动，会话过期返回 401，
    前端清除本地登录态并跳转登录页；活跃会话剩余有效期不足一半时自动
    滑动续期并刷新 Cookie，活跃用户不掉线。
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            token = current_session_token()
            if not token:
                return fail("未登录或登录已失效", 401)

            with Session(engine) as session:
                record = session_service.get_valid_session(session, token)
                if record is None:
                    result = fail("登录已过期，请重新登录", 401)
                    clear_session_cookie(result[0])
                    return result

                user = session.get(User, record.user_id)
                if user is None or not user.is_active:
                    session_service.delete_session(session, token)
                    result = fail("用户不存在或已被停用", 401)
                    clear_session_cookie(result[0])
                    return result
                if admin and not user.is_admin:
                    return fail("需要管理员权限", 403)

                renewed = session_service.touch(session, record)
                g.session = session
                g.user = user
                result = view_func(*args, **kwargs)

            # 会话滑动续期：剩余不足一半时已延长服务端有效期，同步刷新 Cookie
            if renewed:
                body = result[0] if isinstance(result, tuple) else result
                if hasattr(body, "headers"):
                    set_session_cookie(body, token)
            return result

        return wrapper

    return decorator
