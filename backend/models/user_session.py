"""登录会话表模型（Cookie + 服务端会话，不采用登录令牌校验）。"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserSession(SQLModel, table=True):
    """登录会话：登录成功后在服务端落库，浏览器 Cookie 仅保存随机会话标识。

    空闲超过站点配置 session_idle_minutes 未活动即过期；
    活跃会话剩余有效期不足一半时自动滑动续期（活跃用户不掉线）。
    """

    __tablename__ = "user_session"

    id: Optional[int] = Field(default=None, primary_key=True)
    token: str = Field(max_length=64, index=True, unique=True)  # Cookie 中保存的随机会话标识
    user_id: int = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=_utcnow)
    last_active_at: datetime = Field(default_factory=_utcnow)
    expires_at: datetime = Field(default_factory=_utcnow, index=True)
