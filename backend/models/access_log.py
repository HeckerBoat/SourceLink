"""资源块解锁访问记录表模型。"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AccessLog(SQLModel, table=True):
    """记录用户尝试解锁资源块的行为，便于管理员审计。"""

    __tablename__ = "access_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    resource_id: int = Field(index=True)
    success: bool
    created_at: datetime = Field(default_factory=_utcnow)
