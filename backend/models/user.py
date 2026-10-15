"""用户表模型。"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    """平台用户（含管理员）。

    普通用户使用手机号或邮箱注册并登录，username 为空；
    内置管理员使用固定用户名 admin 登录，同时绑定手机号。
    """

    __tablename__ = "user"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: Optional[str] = Field(default=None, max_length=64, index=True, unique=True)
    phone: Optional[str] = Field(default=None, max_length=20, index=True, unique=True)
    email: Optional[str] = Field(default=None, max_length=128, index=True, unique=True)
    password_hash: str = Field(max_length=255)
    is_admin: bool = Field(default=False)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
