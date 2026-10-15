"""验证码发送接口。"""

from flask import Blueprint, current_app
from sqlmodel import Session, select

from ..database import engine
from ..models import User
from ..services import verification
from .common import current_user_id, fail, get_json, ok

bp = Blueprint("verification", __name__)

# 合法的验证码用途；register / reset_password 面向未登录用户公开，绑定类用途要求已登录
ALLOWED_PURPOSES = {"register", "bind_email", "reset_password"}
AUTH_PURPOSES = {"bind_email"}


@bp.post("/verification/send")
def send():
    data = get_json()
    target = (data.get("target") or "").strip()
    channel = data.get("channel")
    purpose = (data.get("purpose") or "register").strip() or "register"

    if purpose not in ALLOWED_PURPOSES:
        return fail("验证码用途非法")
    if purpose in AUTH_PURPOSES and current_user_id() is None:
        return fail("请先登录后再发送绑定验证码", 401)
    # 忘记密码：仅允许向已注册的邮箱发送重置验证码
    if purpose == "reset_password":
        if not verification.EMAIL_PATTERN.match(target):
            return fail("邮箱格式不正确")
        with Session(engine) as session:
            existed = session.exec(select(User).where(User.email == target)).first()
        if existed is None:
            return fail("该邮箱未注册")

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
