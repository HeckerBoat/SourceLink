"""认证业务：注册、登录、可信设备、用户序列化。"""

from datetime import datetime, timezone

from sqlmodel import Session, select

from ..models import TrustedDevice, User
from . import verification
from .security import create_access_token, hash_password, verify_password


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


def issue_token(user: User) -> dict:
    token = create_access_token(user.id, user.is_admin)
    return {"token": token, "user": serialize_user(user)}


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
