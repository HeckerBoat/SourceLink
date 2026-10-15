"""登录会话业务：Cookie + 服务端会话表（需求 10：不采用登录令牌校验）。

- 登录/注册成功后创建会话记录，会话标识通过 HttpOnly Cookie 下发浏览器；
- 空闲超过站点配置 session_idle_minutes 未发起任何请求，会话过期需重新登录；
- 活跃会话剩余有效期不足一半时自动滑动续期，并刷新 Cookie 有效期；
- 修改密码 / 停用或删除用户时删除对应会话，强制重新登录。
"""

import secrets
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from ..models import UserSession
from . import site_config

# Cookie 名称：浏览器仅凭该 Cookie 维持登录态
COOKIE_NAME = "sl_session"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime) -> datetime:
    """SQLite 读出的时间可能丢失时区，统一按 UTC 处理避免比较异常。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _purge_expired(session: Session) -> None:
    now = _utcnow()
    for row in session.exec(select(UserSession)).all():
        if _as_aware(row.expires_at) < now:
            session.delete(row)
    session.commit()


def create_session(session: Session, user_id: int) -> UserSession:
    _purge_expired(session)
    now = _utcnow()
    record = UserSession(
        token=secrets.token_hex(32),
        user_id=user_id,
        created_at=now,
        last_active_at=now,
        expires_at=now + timedelta(minutes=site_config.session_idle_minutes()),
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def get_valid_session(session: Session, token: str) -> UserSession | None:
    """按会话标识查找未过期会话；过期会话直接删除并返回 None。"""
    token = (token or "").strip()
    if not token:
        return None
    record = session.exec(select(UserSession).where(UserSession.token == token)).first()
    if record is None:
        return None
    if _as_aware(record.expires_at) < _utcnow():
        session.delete(record)
        session.commit()
        return None
    return record


def touch(session: Session, record: UserSession) -> bool:
    """滑动续期：剩余有效期不足一半时延长到完整空闲时长；返回是否发生了续期。"""
    now = _utcnow()
    idle = timedelta(minutes=site_config.session_idle_minutes())
    if _as_aware(record.expires_at) - now > idle / 2:
        return False
    record.last_active_at = now
    record.expires_at = now + idle
    session.add(record)
    session.commit()
    return True


def delete_session(session: Session, token: str) -> None:
    token = (token or "").strip()
    if not token:
        return
    record = session.exec(select(UserSession).where(UserSession.token == token)).first()
    if record is not None:
        session.delete(record)
        session.commit()


def delete_user_sessions(session: Session, user_id: int) -> None:
    """强制该用户所有设备重新登录。"""
    for row in session.exec(select(UserSession).where(UserSession.user_id == user_id)).all():
        session.delete(row)
    session.commit()
