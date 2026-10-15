"""滑动验证码记录表模型。"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CaptchaRecord(SQLModel, table=True):
    """滑动验证码的挑战与放行凭证，统一存储。

    - kind=challenge：token 为挑战 ID，answer_x 为缺口正确横坐标，
      用户拖动提交的坐标与之比对（容差内通过），一次性消费；
    - kind=ticket：token 为校验通过后签发的一次性凭证，
      注册 / 新设备登录请求携带该凭证，消费后作废。
    """

    __tablename__ = "captcha_record"

    token: str = Field(primary_key=True, max_length=64)
    kind: str = Field(max_length=16, index=True)
    answer_x: Optional[int] = Field(default=None)
    expires_at: datetime = Field(default_factory=_utcnow, index=True)
    consumed_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)
