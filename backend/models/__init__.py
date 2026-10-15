"""所有 SQLModel 表模型，集中导入以便建表注册表元数据。"""

from .access_log import AccessLog
from .captcha_record import CaptchaRecord
from .feedback import Feedback
from .resource import ResourceBlock
from .site_config import SiteConfig
from .trusted_device import TrustedDevice
from .user import User
from .verification import VerificationCode

__all__ = [
    "AccessLog",
    "CaptchaRecord",
    "Feedback",
    "ResourceBlock",
    "SiteConfig",
    "TrustedDevice",
    "User",
    "VerificationCode",
]
