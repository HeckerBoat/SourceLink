"""资源块表模型。"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ResourceBlock(SQLModel, table=True):
    """商业化虚拟资源块，由管理员新建/编辑/删除。

    用户在资源市场看到已上架的资源块，输入正确的资源块密码后
    才能查看网盘链接；购买链接指向第三方购买页面。
    """

    __tablename__ = "resource_block"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=128, index=True)
    description: Optional[str] = Field(default=None)
    pan_url: str = Field(max_length=512)
    purchase_url: str = Field(max_length=512)
    block_password_hash: str = Field(max_length=255)
    is_published: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
