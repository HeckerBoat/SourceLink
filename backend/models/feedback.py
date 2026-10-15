"""用户反馈表模型。"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Feedback(SQLModel, table=True):
    """用户提交的意见反馈。

    普通用户只能查看自己提交的反馈，管理员可查看全部；
    记录提交者 user_id，展示时由服务层联表带出账号。
    """

    __tablename__ = "feedback"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    content: str = Field(max_length=2000)
    created_at: datetime = Field(default_factory=_utcnow, index=True)
