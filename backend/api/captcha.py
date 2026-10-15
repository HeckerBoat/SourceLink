"""滑动验证码接口：获取拼图挑战、校验拖动坐标。"""

from flask import Blueprint

from sqlmodel import Session

from ..database import engine
from ..services import captcha
from .common import fail, get_json, ok

bp = Blueprint("captcha", __name__)


@bp.post("/captcha/new")
def new_captcha():
    """生成一题滑动拼图验证码（公开接口，供注册与新设备登录使用）。"""
    with Session(engine) as session:
        try:
            data = captcha.create_challenge(session)
        except Exception as exc:
            return fail(str(exc))
    return ok(data)


@bp.post("/captcha/verify")
def verify_captcha():
    """校验拖动坐标；通过则签发一次性凭证 ticket。"""
    data = get_json()
    with Session(engine) as session:
        try:
            ticket = captcha.verify_challenge(session, data.get("challenge_id", ""), data.get("x", 0))
        except captcha.CaptchaError as exc:
            return fail(str(exc))
        except Exception as exc:
            return fail(str(exc))
    return ok({"ticket": ticket}, "验证通过")
