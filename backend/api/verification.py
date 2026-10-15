"""验证码发送接口。"""

import jwt
from flask import Blueprint, current_app, request
from sqlmodel import Session

from ..database import engine
from ..services import verification
from ..services.security import decode_access_token
from .common import fail, get_json, ok

bp = Blueprint("verification", __name__)

# 合法的验证码用途；register 面向未登录用户公开，绑定类用途要求已登录
ALLOWED_PURPOSES = {"register", "bind_email"}
AUTH_PURPOSES = {"bind_email"}


@bp.post("/verification/send")
def send():
    data = get_json()
    target = (data.get("target") or "").strip()
    channel = data.get("channel")
    purpose = (data.get("purpose") or "register").strip() or "register"

    if purpose not in ALLOWED_PURPOSES:
        return fail("验证码用途非法")
    if purpose in AUTH_PURPOSES and _authenticated_user_id() is None:
        return fail("请先登录后再发送绑定验证码", 401)

    try:
        with Session(engine) as session:
            verification.send_code(session, target, channel, purpose=purpose)
    except verification.VerificationError as exc:
        return fail(str(exc))
    except Exception as exc:
        # 渠道异常（如 SMTP 登录失败）只记录后端，前端得到通用提示
        current_app.logger.exception("验证码发送失败: %s", exc)
        return fail("验证码发送失败，请稍后重试或联系管理员")
    return ok(msg="验证码已发送")


def _authenticated_user_id() -> int | None:
    """解析 Authorization 头中的令牌；无效或过期返回 None。"""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else ""
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        return int(payload.get("sub", 0))
    except (jwt.PyJWTError, TypeError, ValueError):
        return None
