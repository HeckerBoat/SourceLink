"""通知渠道：短信与邮件。

- 邮件：配置 SMTP 后真实发送（.env 中配置）；
- 短信：默认 console 模式，验证码直接打印在后端终端（符合日志只进终端的约定），
  aliyun / tencent 为预留接入位，配置厂商密钥后可在此扩展；
- 任何发送异常均向上抛出，由调用方记录到后端日志。
"""

import logging
import smtplib
import ssl
from datetime import datetime
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr

from ..config import Config
from . import site_config

logger = logging.getLogger(__name__)


def send_sms(phone: str, code: str) -> None:
    provider = Config.SMS_PROVIDER.lower()
    if provider == "console":
        logger.info("【短信验证码(console)】手机号=%s 验证码=%s 5分钟内有效", phone, code)
        print(f"\n[SMS-console] 向手机号 {phone} 发送验证码: {code} (5 分钟内有效)\n")
        return

    # 预留：阿里云/腾讯云短信接入需要 SDK 或签名请求，在此根据 provider 实现。
    # 未完成接入前，统一回退到终端打印，避免注册流程不可用。
    logger.warning("短信渠道 %s 尚未完成厂商接入，回退 console 打印", provider)
    print(f"\n[SMS-{provider}-fallback] 向手机号 {phone} 发送验证码: {code}\n")


def send_email(to_email: str, code: str) -> None:
    site_name = site_config.get_config("site_name") or "SourceLink"
    # 验证码有效期（分钟）与站点配置 code_ttl_seconds 保持一致
    try:
        minutes = max(1, int(int(site_config.get_config("code_ttl_seconds") or 300) / 60))
    except (TypeError, ValueError):
        minutes = 5

    if not Config.SMTP_ENABLED or not Config.SMTP_HOST:
        logger.info("【邮箱验证码(console)】邮箱=%s 验证码=%s %s分钟内有效", to_email, code, minutes)
        print(f"\n[EMAIL-console] 向邮箱 {to_email} 发送验证码: {code} ({minutes} 分钟内有效)\n")
        return

    # 需求规定邮件模板：主题「资源链接验证码」，
    # 内容「您的邮箱验证码是[xxxxxx]，有效期xx分钟，请及时验证！」
    html = f"""\
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:480px;margin:auto;
                border:1px solid #eaeaea;border-radius:12px;padding:32px;color:#333;">
      <h2 style="margin-top:0;color:#4f46e5;">{site_name}</h2>
      <p style="font-size:15px;">您的邮箱验证码是[<b style="font-size:26px;letter-spacing:4px;color:#111;">{code}</b>]，有效期{minutes}分钟，请及时验证！</p>
      <p style="color:#888;font-size:13px;">请勿泄露给他人。如非本人操作请忽略此邮件。</p>
    </div>
    """
    _send_html(to_email, "资源链接验证码", html)

    logger.info("邮箱验证码已通过 SMTP 发送至 %s", to_email)


def send_login_alert(account: str, to_email: str | None, device_desc: str, ip: str) -> None:
    """异地/新设备首次登录风险通知邮件；无邮箱或发送失败仅记录后端日志，不影响登录。"""
    site_name = site_config.get_config("site_name") or "SourceLink"
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title = f"【{site_name}】账号登录风险提醒"

    if not to_email:
        logger.warning("【登录风险】账号 %s 于 %s 在新设备首次登录（IP=%s，设备=%s），但该账号未绑定邮箱，无法发送邮件提醒",
                       account, now_text, ip, device_desc)
        print(f"\n[LOGIN-ALERT] 账号 {account} 在新设备首次登录 (IP={ip}, 设备={device_desc})，未绑定邮箱，仅记录终端日志\n")
        return

    if not Config.SMTP_ENABLED or not Config.SMTP_HOST:
        logger.warning("【登录风险(console)】账号 %s 于 %s 新设备首次登录（IP=%s，设备=%s），邮件通道未开启，打印终端",
                       account, now_text, ip, device_desc)
        print(f"\n[LOGIN-ALERT] 账号 {account} 在新设备首次登录 (IP={ip}, 设备={device_desc})，收件邮箱: {to_email}\n")
        return

    html = f"""\
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:480px;margin:auto;
                border:1px solid #eaeaea;border-radius:12px;padding:32px;color:#333;">
      <h2 style="margin-top:0;color:#d97706;">{title}</h2>
      <p>您的账号 <b>{account}</b> 于 <b>{now_text}</b> 在一台新设备上首次登录成功：</p>
      <p style="color:#555;">登录 IP：{ip}<br />设备信息：{device_desc}</p>
      <p style="color:#b91c1c;">若本次登录并非您本人操作，请立即登录平台修改密码。</p>
      <p style="color:#888;font-size:13px;">本邮件由系统自动发送，请勿回复。</p>
    </div>
    """
    try:
        _send_html(to_email, title, html)
        logger.info("新设备登录风险提醒已发送至 %s（账号 %s）", to_email, account)
    except Exception as exc:
        logger.exception("登录风险提醒邮件发送失败（账号 %s）: %s", account, exc)


def _send_html(to_email: str, subject: str, html: str) -> None:
    message = MIMEText(html, "html", "utf-8")
    site_name = site_config.get_config("site_name") or "SourceLink"
    message["From"] = formataddr((str(Header(site_name, "utf-8")), Config.SMTP_FROM))
    message["To"] = to_email
    message["Subject"] = Header(subject, "utf-8")

    context = ssl.create_default_context()
    if Config.SMTP_USE_SSL:
        with smtplib.SMTP_SSL(Config.SMTP_HOST, Config.SMTP_PORT, context=context, timeout=15) as server:
            server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
            server.sendmail(Config.SMTP_FROM, [to_email], message.as_string())
    else:
        with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=15) as server:
            server.starttls(context=context)
            server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
            server.sendmail(Config.SMTP_FROM, [to_email], message.as_string())
