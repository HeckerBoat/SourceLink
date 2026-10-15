"""统一响应与鉴权装饰器。"""

from datetime import datetime, timezone
from functools import wraps
from typing import Any

import jwt
from flask import g, jsonify, request
from sqlmodel import Session

from ..config import Config
from ..database import engine
from ..models import User
from ..services import site_config
from ..services.security import create_access_token, decode_access_token


def ok(data: Any = None, msg: str = "success"):
    return jsonify({"code": 0, "msg": msg, "data": data})


def fail(msg: str = "请求失败", http_status: int = 400, code: int = 1, data: Any = None):
    return jsonify({"code": code, "msg": msg, "data": data}), http_status


def get_json() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def require_auth(admin: bool = False):
    """注入数据库会话与当前用户到 flask.g；admin=True 时额外要求管理员。

    会话滑动续期：剩余有效期不足一半时，在响应头 X-Refresh-Token 下发新令牌，
    前端自动替换，保证活跃用户不掉线；空闲超过 SESSION_IDLE_MINUTES 后令牌过期，
    任何请求都会收到 401 并跳转重新登录。
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else ""
            if not token:
                return fail("未登录或登录已失效", 401)
            try:
                payload = decode_access_token(token)
            except jwt.ExpiredSignatureError:
                return fail("登录已过期，请重新登录", 401)
            except jwt.PyJWTError:
                return fail("登录令牌无效", 401)

            with Session(engine) as session:
                user = session.get(User, int(payload.get("sub", 0)))
                if user is None or not user.is_active:
                    return fail("用户不存在或已被停用", 401)
                if admin and not user.is_admin:
                    return fail("需要管理员权限", 403)
                g.session = session
                g.user = user
                result = view_func(*args, **kwargs)

            # 活跃会话自动续期：令牌剩余不足一半有效期时签发新令牌
            refresh_token = _maybe_refresh(payload)
            if refresh_token is not None:
                body = result[0] if isinstance(result, tuple) else result
                if hasattr(body, "headers"):
                    body.headers["X-Refresh-Token"] = refresh_token
            return result

        return wrapper

    return decorator


def _maybe_refresh(payload: dict) -> str | None:
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)):
        return None
    remain = exp - datetime.now(timezone.utc).timestamp()
    if remain > site_config.session_idle_minutes() * 60 / 2:
        return None
    return create_access_token(int(payload.get("sub", 0)), bool(payload.get("is_admin")))
