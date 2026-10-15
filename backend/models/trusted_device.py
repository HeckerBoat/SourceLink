"""可信设备表模型。"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TrustedDevice(SQLModel, table=True):
    """用户成功登录过的设备（浏览器端持久化的匿名设备 ID）。

    同一 (user_id, device_id) 首次登录视为“异地/新设备”：
    需要先通过滑动验证码，登录成功后写入本表并发送风险邮件；
    之后同一设备再次登录不再要求滑动验证。
    """

    __tablename__ = "trusted_device"
    __table_args__ = (UniqueConstraint("user_id", "device_id", name="uq_user_device"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    device_id: str = Field(max_length=64, index=True)
    device_name: Optional[str] = Field(default=None, max_length=160)
    first_login_at: datetime = Field(default_factory=_utcnow)
    last_login_at: datetime = Field(default_factory=_utcnow)
