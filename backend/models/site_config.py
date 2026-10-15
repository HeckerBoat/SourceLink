"""站点配置表模型（前端可调参数的持久化存储）。"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SiteConfig(SQLModel, table=True):
    """键值对形式的站点配置，管理后台修改后即时生效。"""

    __tablename__ = "site_config"

    id: Optional[int] = Field(default=None, primary_key=True)
    config_key: str = Field(max_length=64, index=True, unique=True)
    config_value: str = Field(default="")
    updated_at: datetime = Field(default_factory=_utcnow)
