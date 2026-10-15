"""验证码表模型（短信 / 邮箱共用）。"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VerificationCode(SQLModel, table=True):
    """注册等场景下发的验证码。

    验证码明文不落库，仅保存 SHA-256 哈希；校验通过后写入 consumed_at
    使其不可重复使用，expires_at 控制有效期。
    """

    __tablename__ = "verification_code"

    id: Optional[int] = Field(default=None, primary_key=True)
    target: str = Field(max_length=128, index=True)
    channel: str = Field(max_length=10, index=True)  # sms / email
    purpose: str = Field(max_length=32, default="register", index=True)
    code_hash: str = Field(max_length=64)
    expires_at: datetime
    consumed_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
