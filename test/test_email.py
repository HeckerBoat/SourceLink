"""163 邮箱 SMTP 发信实测脚本。

直接调用后端 services.notifier.send_email，向 .env 中配置的 163 邮箱
（SMTP_USER，即发件箱自身）发送一封注册验证码邮件，验证授权码与链路可用。

用法（项目根目录）：
    .\\.venv\\Scripts\\python.exe test\\test_email.py
"""

import sys
from pathlib import Path

# 保证可以 import backend 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import Config
from backend.services.notifier import send_email


def main() -> int:
    print(f"SMTP_ENABLED = {Config.SMTP_ENABLED}")
    print(f"SMTP_HOST    = {Config.SMTP_HOST}:{Config.SMTP_PORT} (SSL={Config.SMTP_USE_SSL})")
    print(f"SMTP_USER    = {Config.SMTP_USER}")

    if not Config.SMTP_ENABLED:
        print("[FAIL] SMTP_ENABLED=false，请先在 .env 中开启")
        return 1

    target = Config.SMTP_USER  # 发给自己验证
    print(f"正在向 {target} 发送测试验证码邮件 ...")
    try:
        send_email(target, "888999")
    except Exception as exc:  # noqa: BLE001 - 测试脚本直接展示全部异常
        print(f"[FAIL] 发送失败: {type(exc).__name__}: {exc}")
        return 1

    print(f"[OK] 发送成功，请登录 {target} 查收标题为“注册验证码”的邮件（注意垃圾邮件文件夹）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
