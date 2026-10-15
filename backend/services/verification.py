"""验证码业务：生成、限频发送、校验。"""

import random
import re
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from ..models import VerificationCode
from . import notifier, site_config
from .security import sha256_text

PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


class VerificationError(Exception):
    """业务校验失败，消息可直接返回给前端。"""


def validate_target(target: str, channel: str) -> None:
    if channel == "sms" and not PHONE_PATTERN.match(target):
        raise VerificationError("手机号格式不正确")
    if channel == "email" and not EMAIL_PATTERN.match(target):
        raise VerificationError("邮箱格式不正确")
    if channel not in {"sms", "email"}:
        raise VerificationError("验证码渠道非法")


def send_code(session: Session, target: str, channel: str, purpose: str = "register") -> None:
    validate_target(target, channel)

    # 渠道开关
    if channel == "sms" and site_config.get_config("sms_channel_enabled") != "true":
        raise VerificationError("短信注册渠道已关闭")
    if channel == "email" and site_config.get_config("email_channel_enabled") != "true":
        raise VerificationError("邮箱注册渠道已关闭")

    ttl = int(site_config.get_config("code_ttl_seconds"))
    resend_interval = int(site_config.get_config("code_resend_interval"))

    latest = session.exec(
        select(VerificationCode)
        .where(
            VerificationCode.target == target,
            VerificationCode.channel == channel,
            VerificationCode.purpose == purpose,
        )
        .order_by(VerificationCode.created_at.desc())
    ).first()
    if latest is not None:
        delta = (datetime.now(timezone.utc) - latest.created_at).total_seconds()
        if delta < resend_interval:
            raise VerificationError(f"发送过于频繁，请 {int(resend_interval - delta)} 秒后再试")

    code = f"{random.randint(0, 999999):06d}"
    record = VerificationCode(
        target=target,
        channel=channel,
        purpose=purpose,
        code_hash=sha256_text(code),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl),
    )
    session.add(record)
    session.commit()

    # 发送失败不保留“可用状态”的特殊处理：记录已入库，过期自动失效；异常向上抛由路由打印
    if channel == "sms":
        notifier.send_sms(target, code)
    else:
        notifier.send_email(target, code)


def verify_code(session: Session, target: str, channel: str, code: str, purpose: str = "register") -> bool:
    """校验成功后立即作废该验证码（一次性）。"""
    record = session.exec(
        select(VerificationCode)
        .where(
            VerificationCode.target == target,
            VerificationCode.channel == channel,
            VerificationCode.purpose == purpose,
            VerificationCode.consumed_at.is_(None),
        )
        .order_by(VerificationCode.created_at.desc())
    ).first()

    if record is None:
        return False
    if record.expires_at < datetime.now(timezone.utc):
        return False
    if record.code_hash != sha256_text(code.strip()):
        return False

    record.consumed_at = datetime.now(timezone.utc)
    session.add(record)
    session.commit()
    return True
