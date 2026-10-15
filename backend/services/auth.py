"""认证业务：注册、登录、忘记密码、可信设备、用户序列化、管理员用户管理。"""

from datetime import datetime, timezone

from sqlmodel import Session, select

from ..models import TrustedDevice, User
from . import user_session as session_service
from . import verification
from .security import hash_password, verify_password


class AuthError(Exception):
    """认证业务异常，消息可直接返回给前端。"""


def serialize_user(user: User) -> dict:
    account = user.username or user.phone or user.email or ""
    return {
        "id": user.id,
        "username": user.username,
        "phone": user.phone,
        "email": user.email,
        "account": account,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def register_user(session: Session, channel: str, target: str, code: str, password: str) -> User:
    """短信或邮箱验证码校验通过其一即可注册。"""
    verification.validate_target(target, channel)
    if not password or len(password) < 6 or len(password) > 64:
        raise AuthError("密码长度需为 6-64 位")

    field = "phone" if channel == "sms" else "email"
    existed = session.exec(select(User).where(getattr(User, field) == target)).first()
    if existed is not None:
        raise AuthError("该手机号已注册" if channel == "sms" else "该邮箱已注册")

    if not verification.verify_code(session, target, channel, code):
        raise AuthError("验证码错误或已过期")

    user = User(
        phone=target if channel == "sms" else None,
        email=target if channel == "email" else None,
        password_hash=hash_password(password),
        is_admin=False,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def bind_phone(session: Session, user: User, phone: str) -> User:
    """我的页面绑定/更换手机号：无需短信验证码，格式校验通过且未被他人占用即可绑定，
    绑定后该手机号可作为登录账号。"""
    phone = (phone or "").strip()
    if not verification.PHONE_PATTERN.match(phone):
        raise AuthError("手机号格式不正确")
    existed = session.exec(select(User).where(User.phone == phone)).first()
    if existed is not None and existed.id != user.id:
        raise AuthError("该手机号已被其他账号绑定")
    user.phone = phone
    user.updated_at = datetime.now(timezone.utc)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def bind_email(session: Session, user: User, email: str, code: str) -> User:
    """我的页面绑定邮箱：格式校验 + 邮箱验证码（purpose=bind_email）校验通过即可绑定，
    绑定后该邮箱可作为登录账号。"""
    email = (email or "").strip()
    if not verification.EMAIL_PATTERN.match(email):
        raise AuthError("邮箱格式不正确")
    existed = session.exec(select(User).where(User.email == email)).first()
    if existed is not None and existed.id != user.id:
        raise AuthError("该邮箱已被其他账号绑定")
    if not verification.verify_code(session, email, "email", code, purpose="bind_email"):
        raise AuthError("验证码错误或已过期")
    user.email = email
    user.updated_at = datetime.now(timezone.utc)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def authenticate(session: Session, account: str, password: str) -> User:
    """账号支持用户名 / 手机号 / 邮箱。"""
    account = (account or "").strip()
    if not account:
        raise AuthError("请输入账号")
    user = session.exec(
        select(User).where(
            (User.username == account) | (User.phone == account) | (User.email == account)
        )
    ).first()
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("账号或密码错误")
    if not user.is_active:
        raise AuthError("账号已被停用")
    user.updated_at = datetime.now(timezone.utc)
    session.add(user)
    session.commit()
    return user


def reset_password(session: Session, email: str, code: str, password: str) -> User:
    """忘记密码：邮箱验证码（purpose=reset_password）校验通过后重置密码，
    并删除该用户全部登录会话，强制所有设备用新密码重新登录。"""
    email = (email or "").strip()
    if not verification.EMAIL_PATTERN.match(email):
        raise AuthError("邮箱格式不正确")
    if not password or len(password) < 6 or len(password) > 64:
        raise AuthError("密码长度需为 6-64 位")
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        raise AuthError("该邮箱未注册")
    if not verification.verify_code(session, email, "email", code, purpose="reset_password"):
        raise AuthError("验证码错误或已过期")
    user.password_hash = hash_password(password)
    user.updated_at = datetime.now(timezone.utc)
    session.add(user)
    session.commit()
    session_service.delete_user_sessions(session, user.id)
    session.refresh(user)
    return user


def normalize_device_id(device_id: str | None) -> str:
    return (device_id or "").strip()[:64]


def is_trusted_device(session: Session, user_id: int, device_id: str) -> TrustedDevice | None:
    device_id = normalize_device_id(device_id)
    if not device_id:
        return None
    return session.exec(
        select(TrustedDevice).where(
            TrustedDevice.user_id == user_id, TrustedDevice.device_id == device_id
        )
    ).first()


def trust_device(session: Session, user_id: int, device_id: str, device_name: str | None = None) -> TrustedDevice:
    """登记可信设备；已存在则刷新最近登录时间。"""
    device_id = normalize_device_id(device_id)
    record = is_trusted_device(session, user_id, device_id)
    now = datetime.now(timezone.utc)
    if record is not None:
        record.last_login_at = now
        if device_name and not record.device_name:
            record.device_name = device_name[:160]
        session.add(record)
        session.commit()
        session.refresh(record)
        return record

    record = TrustedDevice(
        user_id=user_id,
        device_id=device_id,
        device_name=(device_name or "")[:160] or None,
        first_login_at=now,
        last_login_at=now,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


# ---------------- 管理员用户管理（新建 / 查看 / 编辑 / 删除客户账户） ----------------

def _check_unique(session: Session, field: str, value: str, exclude_id: int | None = None) -> None:
    existed = session.exec(select(User).where(getattr(User, field) == value)).first()
    if existed is not None and existed.id != exclude_id:
        label = {"username": "用户名", "phone": "手机号", "email": "邮箱"}[field]
        raise AuthError(f"该{label}已被占用")


def admin_list_users(session: Session, keyword: str = "") -> list[dict]:
    keyword = (keyword or "").strip()
    query = select(User).order_by(User.created_at.desc())
    if keyword:
        query = query.where(
            (User.username == keyword) | (User.phone == keyword) | (User.email == keyword)
        )
    return [serialize_user(u) for u in session.exec(query).all()]


def admin_create_user(session: Session, data: dict) -> User:
    """管理员新建客户账户：用户名 / 手机号 / 邮箱三选一作为登录账号 + 初始密码。"""
    username = (data.get("username") or "").strip()
    phone = (data.get("phone") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    if not any([username, phone, email]):
        raise AuthError("用户名、手机号、邮箱至少填写一项作为登录账号")
    if not password or len(password) < 6 or len(password) > 64:
        raise AuthError("密码长度需为 6-64 位")
    if username and (len(username) > 64 or not username.replace("_", "").isalnum()):
        raise AuthError("用户名仅支持字母、数字、下划线，最长 64 位")
    if phone and not verification.PHONE_PATTERN.match(phone):
        raise AuthError("手机号格式不正确")
    if email and not verification.EMAIL_PATTERN.match(email):
        raise AuthError("邮箱格式不正确")

    for field, value in (("username", username), ("phone", phone), ("email", email)):
        if value:
            _check_unique(session, field, value)

    user = User(
        username=username or None,
        phone=phone or None,
        email=email or None,
        password_hash=hash_password(password),
        is_admin=False,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _require_editable(target: User | None) -> User:
    if target is None:
        raise AuthError("用户不存在")
    if target.is_admin:
        raise AuthError("不能操作管理员账户")
    return target


def admin_update_user(session: Session, user_id: int, data: dict) -> User:
    """管理员编辑客户账户：登录账号（用户名/手机号/邮箱）、状态、重置密码。"""
    user = _require_editable(session.get(User, user_id))
    changed = False

    for field, label, pattern in (
        ("username", "用户名", None),
        ("phone", "手机号", verification.PHONE_PATTERN),
        ("email", "邮箱", verification.EMAIL_PATTERN),
    ):
        if field not in data:
            continue
        value = (data.get(field) or "").strip()
        if value:
            if field == "username" and (len(value) > 64 or not value.replace("_", "").isalnum()):
                raise AuthError("用户名仅支持字母、数字、下划线，最长 64 位")
            if pattern is not None and not pattern.match(value):
                raise AuthError(f"{label}格式不正确")
            _check_unique(session, field, value, exclude_id=user.id)
            setattr(user, field, value)
        else:
            # 用户名/手机号/邮箱允许清空，但三者不能同时为空
            setattr(user, field, None)
        changed = True

    if not any([user.username, user.phone, user.email]):
        raise AuthError("用户名、手机号、邮箱至少保留一项作为登录账号")

    password = (data.get("password") or "").strip()
    if password:
        if len(password) < 6 or len(password) > 64:
            raise AuthError("密码长度需为 6-64 位")
        user.password_hash = hash_password(password)
        changed = True

    if "is_active" in data:
        user.is_active = bool(data["is_active"])
        changed = True

    if changed:
        user.updated_at = datetime.now(timezone.utc)
        session.add(user)
        session.commit()
        # 重置密码或停用后强制重新登录
        if password or not user.is_active:
            session_service.delete_user_sessions(session, user.id)
    session.refresh(user)
    return user


def admin_delete_user(session: Session, user_id: int) -> None:
    """管理员删除客户账户：同时清理其登录会话与可信设备；反馈与访问记录保留为历史。"""
    user = _require_editable(session.get(User, user_id))
    session_service.delete_user_sessions(session, user.id)
    for device in session.exec(select(TrustedDevice).where(TrustedDevice.user_id == user.id)).all():
        session.delete(device)
    session.delete(user)
    session.commit()
