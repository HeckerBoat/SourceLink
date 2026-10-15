"""全局配置。

敏感配置（密钥、SMTP 密码、短信厂商密钥）从项目根目录的 .env 文件读取；
站点级可调参数（站点名称、注册开关等）存放在数据库 site_config 表中，
由管理后台动态修改，服务启动时加载。
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _get_bool(key: str, default: bool = False) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    # 服务监听地址
    HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    PORT = int(os.getenv("FLASK_PORT", "5000"))

    # Flask 密钥 / 密码二次哈希的 pepper（生产环境务必在 .env 中配置）
    SECRET_KEY = os.getenv("SECRET_KEY", "sourcelink-dev-secret-key")
    PASSWORD_PEPPER = os.getenv("PASSWORD_PEPPER", "sourcelink-dev-pepper")

    # JWT
    JWT_ALGORITHM = "HS256"
    # 会话空闲过期时间（分钟）：超过该时长未向服务器发起任何请求，令牌过期需重新登录；
    # 活跃会话在每次请求时自动滑动续期（剩余不足一半时签发新令牌）
    SESSION_IDLE_MINUTES = int(os.getenv("SESSION_IDLE_MINUTES", "60"))

    # SQLite 数据库（统一放在 db 目录）
    DB_PATH = BASE_DIR / "db" / "sourcelink.db"
    DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

    # 初始化管理员（需求规定的账户）
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "1q2w3e4r")
    ADMIN_PHONE = os.getenv("ADMIN_PHONE", "11111111111")

    # 邮件 SMTP
    SMTP_ENABLED = _get_bool("SMTP_ENABLED", False)
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
    SMTP_USE_SSL = _get_bool("SMTP_USE_SSL", True)
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM = os.getenv("SMTP_FROM", "") or SMTP_USER

    # 短信渠道：console=打印到终端（默认，便于开发调试）；aliyun/tencent=预留厂商接入
    SMS_PROVIDER = os.getenv("SMS_PROVIDER", "console")
    SMS_ACCESS_KEY = os.getenv("SMS_ACCESS_KEY", "")
    SMS_SECRET_KEY = os.getenv("SMS_SECRET_KEY", "")
    SMS_SIGN_NAME = os.getenv("SMS_SIGN_NAME", "SourceLink")
    SMS_TEMPLATE_CODE = os.getenv("SMS_TEMPLATE_CODE", "")

    # 前端构建产物目录
    FRONTEND_DIST = BASE_DIR / "Frontend" / "dist"
