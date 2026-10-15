"""安全工具：密码二次哈希与 JWT 令牌。

二次哈希策略：
1. 第一层使用服务端 pepper 对明文密码做 SHA-256（防止数据库泄露后被直接彩虹表破解）；
2. 第二层使用 werkzeug 的 PBKDF2-SHA256（每用户独立随机盐 + 高迭代次数）抵御暴力破解。

直接读取 Config 而非 current_app，保证在脚本（如初始化数据库）无应用上下文时也能使用。
"""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from werkzeug.security import check_password_hash, generate_password_hash

from ..config import Config
from . import site_config

logger = logging.getLogger(__name__)


def _pre_hash(password: str) -> str:
    return hashlib.sha256(f"{Config.PASSWORD_PEPPER}${password}".encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    return generate_password_hash(_pre_hash(password), method="pbkdf2:sha256", salt_length=16)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return check_password_hash(password_hash, _pre_hash(password))
    except Exception as exc:
        logger.exception("密码校验异常: %s", exc)
        return False


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def create_access_token(user_id: int, is_admin: bool) -> str:
    """签发会话令牌，有效期 = 会话空闲时长（数据库 session_idle_minutes，默认 60 分钟）。

    每次携带令牌的成功请求会在剩余有效期不足一半时自动续期
    （通过响应头下发新令牌），从而实现“无操作 N 小时失效、活跃不掉线”。
    """
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "is_admin": is_admin,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=site_config.session_idle_minutes()),
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm=Config.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, Config.SECRET_KEY, algorithms=[Config.JWT_ALGORITHM])
