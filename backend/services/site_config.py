"""站点配置服务：管理后台可改的参数存数据库，启动时加载并对外暴露。"""

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from ..config import Config
from ..models import SiteConfig

# 默认值（首次启动写入数据库；session_idle_minutes 种子值取自 .env，之后以后台修改为准）
DEFAULT_CONFIG: dict[str, str] = {
    "site_name": "SourceLink 资源托管平台",
    "register_enabled": "true",          # 是否开放注册
    "sms_channel_enabled": "true",       # 是否开放短信注册渠道
    "email_channel_enabled": "true",     # 是否开放邮箱注册渠道
    "code_ttl_seconds": "300",           # 验证码有效期（秒）
    "code_resend_interval": "60",        # 同一目标重发间隔（秒）
    "session_idle_minutes": str(Config.SESSION_IDLE_MINUTES),  # 会话空闲失效时长（分钟）
    "resource_ttl_months": "0",          # 资源有效期-月（0 表示不限制）
    "resource_ttl_days": "0",            # 资源有效期-天
    "resource_ttl_hours": "0",           # 资源有效期-小时
}

# session_idle_minutes 合法范围（分钟）
SESSION_IDLE_MIN = 5
SESSION_IDLE_MAX = 10080  # 7 天

# 资源有效期合法范围（月/天/小时）
RESOURCE_TTL_MONTHS_MAX = 120
RESOURCE_TTL_DAYS_MAX = 3650
RESOURCE_TTL_HOURS_MAX = 87600

# 可对未登录用户公开的配置键（同步到前端）
PUBLIC_KEYS = {
    "site_name",
    "register_enabled",
    "sms_channel_enabled",
    "email_channel_enabled",
}

_cache: dict[str, str] = {}


def load_to_cache(session: Session) -> dict[str, str]:
    """服务启动时从数据库读取全部配置到内存缓存。"""
    _cache.clear()
    _cache.update(DEFAULT_CONFIG)
    for item in session.exec(select(SiteConfig)).all():
        _cache[item.config_key] = item.config_value
    return dict(_cache)


def all_config() -> dict[str, str]:
    return dict(_cache) if _cache else dict(DEFAULT_CONFIG)


def get_config(key: str) -> str:
    return _cache.get(key, DEFAULT_CONFIG.get(key, ""))


def session_idle_minutes() -> int:
    """会话空闲失效时长（分钟），读取数据库配置；非法值回退默认 60。"""
    try:
        value = int(get_config("session_idle_minutes"))
    except (TypeError, ValueError):
        return 60
    return max(SESSION_IDLE_MIN, min(SESSION_IDLE_MAX, value))


def resource_ttl() -> dict[str, int]:
    """资源有效期配置（月/天/小时），非法值回退 0。"""
    def _int(key: str) -> int:
        try:
            return int(get_config(key))
        except (TypeError, ValueError):
            return 0

    months = max(0, min(RESOURCE_TTL_MONTHS_MAX, _int("resource_ttl_months")))
    days = max(0, min(RESOURCE_TTL_DAYS_MAX, _int("resource_ttl_days")))
    hours = max(0, min(RESOURCE_TTL_HOURS_MAX, _int("resource_ttl_hours")))
    return {"months": months, "days": days, "hours": hours}


def is_resource_expired(created_at: datetime | None) -> bool:
    """根据创建日期 + 资源有效期配置判定是否过期。

    有效期三项都为 0 表示永久有效（不过期）。
    过期时间点 = created_at + months*30 天 + days 天 + hours 小时，
    当前时间晚于该点即视为过期。
    """
    if created_at is None:
        return False
    ttl = resource_ttl()
    if ttl["months"] == 0 and ttl["days"] == 0 and ttl["hours"] == 0:
        return False
    delta = timedelta(days=ttl["months"] * 30 + ttl["days"], hours=ttl["hours"])
    expire_at = created_at + delta
    return datetime.now(timezone.utc) > expire_at


def public_config() -> dict[str, str]:
    return {key: get_config(key) for key in PUBLIC_KEYS}


def update_config(session: Session, data: dict[str, str]) -> dict[str, str]:
    for key, value in data.items():
        if key not in DEFAULT_CONFIG:
            continue
        row = session.exec(select(SiteConfig).where(SiteConfig.config_key == key)).first()
        text_value = "true" if value is True else "false" if value is False else str(value)
        if row is None:
            row = SiteConfig(config_key=key, config_value=text_value)
        else:
            row.config_value = text_value
        session.add(row)
        _cache[key] = text_value
    session.commit()
    return all_config()


def seed_defaults(session: Session) -> None:
    """首次启动时把默认配置写入数据库。"""
    existed = {row.config_key for row in session.exec(select(SiteConfig)).all()}
    changed = False
    for key, value in DEFAULT_CONFIG.items():
        if key not in existed:
            session.add(SiteConfig(config_key=key, config_value=value))
            changed = True
    if changed:
        session.commit()
