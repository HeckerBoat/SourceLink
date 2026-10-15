"""认证相关接口：公开配置、注册、登录、退出登录、忘记密码、当前用户。"""

from flask import Blueprint, current_app, g, request
from sqlmodel import Session

from ..database import engine
from ..services import auth as auth_service
from ..services import captcha, site_config
from ..services import notifier
from ..services import user_session as session_service
from .common import (
    clear_session_cookie,
    current_session_token,
    fail,
    get_json,
    ok,
    require_auth,
    set_session_cookie,
)

bp = Blueprint("auth", __name__)

# 业务码：需要滑动验证码（新设备首次登录）
CODE_NEED_CAPTCHA = 4011


def _login_response(user_id: int, user_data: dict, session_token: str, msg: str):
    """登录/注册成功响应：通过 HttpOnly Cookie 下发服务端会话标识。"""
    response = ok({"user": user_data}, msg)
    set_session_cookie(response, session_token)
    return response


@bp.get("/config/public")
def public_config():
    return ok(site_config.public_config())


@bp.post("/auth/register")
def register():
    data = get_json()
    channel = data.get("channel")
    target = (data.get("target") or "").strip()
    code = (data.get("code") or "").strip()
    password = data.get("password") or ""
    device_id = auth_service.normalize_device_id(data.get("device_id"))

    if site_config.get_config("register_enabled") != "true":
        return fail("当前已关闭注册")

    with Session(engine) as session:
        # 注册必须先通过滑动拼图验证码（防人机）
        if not captcha.consume_ticket(session, data.get("captcha_ticket", "")):
            return fail("请先完成滑动验证码校验")

        try:
            user = auth_service.register_user(session, channel, target, code, password)
            # 注册即登录：当前设备记为可信设备，之后登录不再要求滑动验证
            if device_id:
                auth_service.trust_device(session, user.id, device_id, request.headers.get("User-Agent", ""))
            record = session_service.create_session(session, user.id)
            user_id, user_data = user.id, auth_service.serialize_user(user)
        except Exception as exc:
            return fail(str(exc))

    current_app.logger.info("新用户注册成功: %s (%s)", target, channel)
    return _login_response(user_id, user_data, record.token, "注册成功")


@bp.post("/auth/login")
def login():
    data = get_json()
    device_id = auth_service.normalize_device_id(data.get("device_id"))
    ticket = (data.get("captcha_ticket") or "").strip()

    with Session(engine) as session:
        try:
            user = auth_service.authenticate(session, data.get("account", ""), data.get("password", ""))
        except Exception as exc:
            return fail(str(exc), 401)

        # 异地/新设备首次登录：必须先通过滑动验证码，成功后登记设备并发送风险邮件
        trusted = auth_service.is_trusted_device(session, user.id, device_id)
        if trusted is None:
            try:
                if not captcha.consume_ticket(session, ticket):
                    return jsonify_need_captcha()
            except Exception as exc:
                current_app.logger.exception("滑动验证码校验异常: %s", exc)
                return fail("滑动验证校验失败，请重试", 401)

            device_desc = _device_desc(device_id)
            auth_service.trust_device(session, user.id, device_id, request.headers.get("User-Agent", ""))
            notifier.send_login_alert(
                account=auth_service.serialize_user(user).get("account", f"用户#{user.id}"),
                to_email=user.email,
                device_desc=device_desc,
                ip=request.remote_addr or "未知",
            )
        else:
            auth_service.trust_device(session, user.id, device_id)

        record = session_service.create_session(session, user.id)
        user_id, user_data = user.id, auth_service.serialize_user(user)

    return _login_response(user_id, user_data, record.token, "登录成功")


@bp.post("/auth/logout")
def logout():
    """退出登录：删除服务端会话并清除浏览器 Cookie。"""
    with Session(engine) as session:
        session_service.delete_session(session, current_session_token())
    response = ok(msg="已退出登录")
    clear_session_cookie(response)
    return response


@bp.post("/auth/forgot-password")
def forgot_password():
    """忘记密码：邮箱验证码（purpose=reset_password）校验通过后重置密码。"""
    data = get_json()
    try:
        with Session(engine) as session:
            user = auth_service.reset_password(
                session,
                data.get("email", ""),
                (data.get("code") or "").strip(),
                data.get("password") or "",
            )
    except auth_service.AuthError as exc:
        return fail(str(exc))
    current_app.logger.info("用户通过忘记密码重置密码: user_id=%s email=%s", user.id, user.email)
    return ok(msg="密码已重置，请使用新密码登录")


def jsonify_need_captcha():
    return fail("检测到新设备登录，请先完成滑动验证码校验", 200, CODE_NEED_CAPTCHA, {"need_captcha": True})


def _device_desc(device_id: str) -> str:
    ua = (request.headers.get("User-Agent") or "").strip()
    short_ua = ua[:120] + ("…" if len(ua) > 120 else "")
    return f"设备标识 {device_id or '未提供'}；UA：{short_ua or '未知'}"


@bp.get("/auth/me")
@require_auth()
def me():
    return ok(auth_service.serialize_user(g.user))


@bp.post("/auth/bind-phone")
@require_auth()
def bind_phone():
    """我的页面绑定/更换手机号：无需短信验证码，格式校验通过即可绑定。"""
    phone = (get_json().get("phone") or "").strip()
    try:
        user = auth_service.bind_phone(g.session, g.user, phone)
    except auth_service.AuthError as exc:
        return fail(str(exc))
    current_app.logger.info("用户绑定手机号: user_id=%s phone=%s", g.user.id, phone)
    return ok(auth_service.serialize_user(user), "手机号绑定成功")


@bp.post("/auth/bind-email")
@require_auth()
def bind_email():
    """我的页面绑定邮箱：邮箱格式校验通过后发送验证码（purpose=bind_email），验证通过即可绑定。"""
    data = get_json()
    email = (data.get("email") or "").strip()
    code = (data.get("code") or "").strip()
    try:
        user = auth_service.bind_email(g.session, g.user, email, code)
    except auth_service.AuthError as exc:
        return fail(str(exc))
    current_app.logger.info("用户绑定邮箱: user_id=%s email=%s", g.user.id, email)
    return ok(auth_service.serialize_user(user), "邮箱绑定成功")
