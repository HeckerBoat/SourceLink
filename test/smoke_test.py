"""SourceLink 接口冒烟测试（需先启动 app.py）。

覆盖流程：
公开配置 -> 管理员登录（新设备滑动验证 + 可信设备免验证）-> 资源块 CRUD
-> 发送验证码 -> 滑动验证码 -> 普通用户注册（携带滑动凭证）-> 用户登录
-> 资源列表 -> 错误/正确资源块密码解锁 -> 免密直显 -> 访问记录 -> 权限校验
-> 用户反馈（普通用户仅见自己的 / 管理员见全部）-> 会话空闲续期

运行：
    .\\.venv\\Scripts\\python.exe test\\smoke_test.py
"""

import json
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# 允许直接从项目根运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select  # noqa: E402

from backend.config import Config  # noqa: E402
from backend.database import engine  # noqa: E402
from backend.models import ResourceBlock, UserSession, VerificationCode  # noqa: E402
from backend.services.security import sha256_text  # noqa: E402

BASE = "http://127.0.0.1:5000/api"

passed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" -> {detail}" if detail else ""))
    if not condition:
        raise AssertionError(name)
    passed += 1


def cleanup() -> None:
    """清理上一次冒烟测试残留的资源块，使脚本可重复运行。"""
    with Session(engine) as session:
        stale = session.exec(
            select(ResourceBlock).where(
                (ResourceBlock.name.like("自动化测试资源%")) | (ResourceBlock.name == "待删除资源")
            )
        ).all()
        for item in stale:
            session.delete(item)
        session.commit()


def solve_captcha() -> str:
    """完整走一遍滑动验证码：获取拼图 -> 查库取正确坐标 -> 换取一次性凭证。"""
    r = requests.post(f"{BASE}/captcha/new", timeout=10)
    assert r.json()["code"] == 0, "获取滑动验证码失败"
    challenge_id = r.json()["data"]["challenge_id"]
    with sqlite3.connect(Config.DB_PATH) as conn:
        row = conn.execute(
            "SELECT answer_x FROM captcha_record WHERE token = ?", (challenge_id,)
        ).fetchone()
    assert row is not None, "滑动验证码挑战未落库"
    r = requests.post(f"{BASE}/captcha/verify", json={"challenge_id": challenge_id, "x": row[0]}, timeout=10)
    assert r.json()["code"] == 0, "滑动验证码校验失败"
    return r.json()["data"]["ticket"]


def main() -> None:
    cleanup()
    suffix = str(int(time.time()))[-8:]
    phone = "139" + suffix  # 3 位号段 + 8 位 = 11 位手机号
    email = f"user{suffix}@example.com"
    block_password = "res-pass-123"
    admin_device = "smoke-admin-device"
    user_device = "smoke-user-device"

    # 1. 公开配置
    r = requests.get(f"{BASE}/config/public", timeout=10)
    body = r.json()
    check("公开配置可访问", body["code"] == 0 and "site_name" in body["data"])

    # 1b. 滑动验证码接口
    r = requests.post(f"{BASE}/captcha/new", timeout=10)
    body = r.json()
    check("获取滑动拼图验证码", body["code"] == 0 and "background" in body["data"])
    wrong_x = requests.post(
        f"{BASE}/captcha/verify",
        json={"challenge_id": body["data"]["challenge_id"], "x": 999},
        timeout=10,
    )
    check("滑动验证错误坐标被拒", wrong_x.json()["code"] == 1)

    # 2. 管理员登录：新设备首次登录必须先通过滑动验证
    r = requests.post(f"{BASE}/auth/login", json={"account": "admin", "password": "1q2w3e4r"}, timeout=10)
    body = r.json()
    check("新设备登录要求滑动验证", body["code"] == 4011, body.get("msg", ""))

    ticket = solve_captcha()
    r = requests.post(
        f"{BASE}/auth/login",
        json={"account": "admin", "password": "1q2w3e4r", "device_id": admin_device, "captcha_ticket": ticket},
        timeout=10,
    )
    body = r.json()
    check("携带滑动凭证后新设备登录成功", body["code"] == 0, body.get("msg", ""))
    check("登录响应不下发令牌（改用 Cookie 会话）", "token" not in body["data"])
    check("登录成功种下会话 Cookie", bool(r.cookies.get("sl_session")))
    admin_ck = {"sl_session": r.cookies.get("sl_session")}
    check("管理员标记正确", body["data"]["user"]["is_admin"] is True)
    check("管理员手机已绑定", body["data"]["user"]["phone"] == "11111111111")

    # 2b. 可信设备再次登录不再要求滑动验证
    r = requests.post(
        f"{BASE}/auth/login",
        json={"account": "admin", "password": "1q2w3e4r", "device_id": admin_device},
        timeout=10,
    )
    check("同设备再次登录免滑动验证", r.json()["code"] == 0)

    # 3. 错误密码登录
    r = requests.post(f"{BASE}/auth/login", json={"account": "admin", "password": "wrong"}, timeout=10)
    check("错误密码被拒绝", r.status_code == 401 and r.json()["code"] == 1)

    # 4. 管理员创建资源块
    payload = {
        "name": f"自动化测试资源 {suffix}",
        "description": "冒烟测试自动创建的资源",
        "pan_url": "https://pan.example.com/s/test-resource",
        "purchase_url": "https://buy.example.com/item/test-resource",
        "block_password": block_password,
        "is_published": True,
    }
    r = requests.post(f"{BASE}/admin/resources", json=payload, cookies=admin_ck, timeout=10)
    body = r.json()
    check("管理员创建资源块成功", body["code"] == 0, body.get("msg", ""))
    resource_id = body["data"]["id"]
    check("列表数据不泄露块密码哈希", "block_password_hash" not in body["data"])

    # 5. 创建用于删除的资源块
    r = requests.post(
        f"{BASE}/admin/resources",
        json={
            "name": "待删除资源",
            "pan_url": "https://pan.example.com/s/to-delete",
            "purchase_url": "https://buy.example.com/to-delete",
            "block_password": "pw",
        },
        cookies=admin_ck,
        timeout=10,
    )
    delete_id = r.json()["data"]["id"]

    # 6. 编辑资源块（不修改密码）
    r = requests.put(
        f"{BASE}/admin/resources/{resource_id}",
        json={"name": payload["name"] + "-改", "description": "描述已更新"},
        cookies=admin_ck,
        timeout=10,
    )
    check("编辑资源块成功", r.json()["code"] == 0 and r.json()["data"]["name"].endswith("-改"))

    # 7. 发送短信验证码（console 模式，验证码打印在后端终端）
    r = requests.post(f"{BASE}/verification/send", json={"target": phone, "channel": "sms"}, timeout=10)
    check("短信验证码发送成功（console）", r.json()["code"] == 0, r.json().get("msg", ""))

    # 8. 非法手机号格式
    r = requests.post(f"{BASE}/verification/send", json={"target": "123", "channel": "sms"}, timeout=10)
    check("非法手机号被拦截", r.json()["code"] == 1)

    # 9. 重发限频
    r = requests.post(f"{BASE}/verification/send", json={"target": phone, "channel": "sms"}, timeout=10)
    check("60 秒重发限制生效", r.json()["code"] == 1)

    # 10. 白盒写入一条已知验证码（真实发送的验证码只在终端，模拟用户收到 246810）
    code = "246810"
    with Session(engine) as session:
        session.add(
            VerificationCode(
                target=phone,
                channel="sms",
                purpose="register",
                code_hash=sha256_text(code),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            )
        )
        session.commit()

    # 11. 未通过滑动验证注册被拒
    r = requests.post(
        f"{BASE}/auth/register",
        json={"channel": "sms", "target": phone, "code": code, "password": "user-pass-1"},
        timeout=10,
    )
    check("未通过滑动验证注册被拒", r.json()["code"] == 1, r.json().get("msg", ""))

    # 12. 错误验证码注册被拒
    register_ticket = solve_captcha()
    r = requests.post(
        f"{BASE}/auth/register",
        json={
            "channel": "sms",
            "target": phone,
            "code": "000000",
            "password": "user-pass-1",
            "captcha_ticket": register_ticket,
            "device_id": user_device,
        },
        timeout=10,
    )
    check("错误验证码注册被拒", r.json()["code"] == 1)

    # 13. 正确验证码 + 滑动凭证注册成功（短信渠道）
    register_ticket = solve_captcha()
    r = requests.post(
        f"{BASE}/auth/register",
        json={
            "channel": "sms",
            "target": phone,
            "code": code,
            "password": "user-pass-1",
            "captcha_ticket": register_ticket,
            "device_id": user_device,
        },
        timeout=10,
    )
    body = r.json()
    check("短信验证码注册成功", body["code"] == 0, body.get("msg", ""))
    check("注册后自动登录种下会话 Cookie", bool(r.cookies.get("sl_session")))

    # 14. 同一手机号不可重复注册（验证码一次性，上一步已作废；这里再准备一条）
    with Session(engine) as session:
        session.add(
            VerificationCode(
                target=phone,
                channel="sms",
                purpose="register",
                code_hash=sha256_text(code),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            )
        )
        session.commit()
    repeat_ticket = solve_captcha()
    r = requests.post(
        f"{BASE}/auth/register",
        json={
            "channel": "sms",
            "target": phone,
            "code": code,
            "password": "user-pass-1",
            "captcha_ticket": repeat_ticket,
        },
        timeout=10,
    )
    check("重复手机号注册被拒", r.json()["code"] == 1)

    # 15. 邮箱渠道注册（验证码由本测试直接写库构造；
    #     注意：.env 开启真实 SMTP 时，本步会向 example.com 真实发信一次并退信，属预期）
    r = requests.post(f"{BASE}/verification/send", json={"target": email, "channel": "email"}, timeout=10)
    check("邮箱验证码发送成功", r.json()["code"] == 0, r.json().get("msg", ""))
    with Session(engine) as session:
        session.add(
            VerificationCode(
                target=email,
                channel="email",
                purpose="register",
                code_hash=sha256_text(code),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            )
        )
        session.commit()
    email_ticket = solve_captcha()
    r = requests.post(
        f"{BASE}/auth/register",
        json={
            "channel": "email",
            "target": email,
            "code": code,
            "password": "user-pass-1",
            "captcha_ticket": email_ticket,
            "device_id": user_device,
        },
        timeout=10,
    )
    check("邮箱验证码注册成功", r.json()["code"] == 0, r.json().get("msg", ""))

    # 16. 普通用户登录：注册设备为可信设备，直接成功；陌生设备要求滑动验证
    r = requests.post(
        f"{BASE}/auth/login",
        json={"account": phone, "password": "user-pass-1", "device_id": user_device},
        timeout=10,
    )
    body = r.json()
    check("普通用户同设备登录免验证", body["code"] == 0)
    user_ck = {"sl_session": r.cookies.get("sl_session")}
    check("普通用户非管理员", body["data"]["user"]["is_admin"] is False)

    r = requests.post(
        f"{BASE}/auth/login",
        json={"account": phone, "password": "user-pass-1", "device_id": "smoke-other-device"},
        timeout=10,
    )
    check("陌生设备登录要求滑动验证", r.json()["code"] == 4011)

    # 16b. 我的页面绑定手机号：邮箱注册用户无需短信验证码即可绑定，之后可用手机号登录
    r = requests.post(
        f"{BASE}/auth/login",
        json={"account": email, "password": "user-pass-1", "device_id": user_device},
        timeout=10,
    )
    check("邮箱用户登录成功", r.json()["code"] == 0)
    email_ck = {"sl_session": r.cookies.get("sl_session")}
    bind_phone_num = "138" + suffix  # 与短信注册用户（139 号段）不同的合法手机号
    r = requests.post(f"{BASE}/auth/bind-phone", json={"phone": "123"}, cookies=email_ck, timeout=10)
    check("绑定非法格式手机号被拒", r.json()["code"] == 1)
    r = requests.post(f"{BASE}/auth/bind-phone", json={"phone": "11111111111"}, cookies=email_ck, timeout=10)
    check("绑定管理员手机号被拒（已被占用）", r.json()["code"] == 1)
    r = requests.post(f"{BASE}/auth/bind-phone", json={"phone": phone}, cookies=email_ck, timeout=10)
    check("绑定他人手机号被拒", r.json()["code"] == 1)
    r = requests.post(f"{BASE}/auth/bind-phone", json={"phone": bind_phone_num}, timeout=10)
    check("未登录绑定手机号 401", r.status_code == 401)
    r = requests.post(f"{BASE}/auth/bind-phone", json={"phone": bind_phone_num}, cookies=email_ck, timeout=10)
    body = r.json()
    check("邮箱用户绑定手机号成功", body["code"] == 0 and body["data"]["phone"] == bind_phone_num)
    r = requests.post(
        f"{BASE}/auth/login",
        json={"account": bind_phone_num, "password": "user-pass-1", "device_id": user_device},
        timeout=10,
    )
    check("绑定后可用手机号登录", r.json()["code"] == 0)

    # 16c. 我的页面绑定邮箱：需登录发送 bind_email 验证码，验证通过即可绑定
    bind_email_addr = f"bind{suffix}@example.com"
    r = requests.post(
        f"{BASE}/verification/send",
        json={"target": bind_email_addr, "channel": "email", "purpose": "bind_email"},
        timeout=10,
    )
    check("未登录发送绑定邮箱验证码 401", r.status_code == 401)
    r = requests.post(
        f"{BASE}/verification/send",
        json={"target": bind_email_addr, "channel": "email", "purpose": "hack"},
        cookies=user_ck,
        timeout=10,
    )
    check("非法验证码用途被拒", r.json()["code"] == 1)
    r = requests.post(
        f"{BASE}/verification/send",
        json={"target": bind_email_addr, "channel": "email", "purpose": "bind_email"},
        cookies=user_ck,
        timeout=10,
    )
    check("登录后发送绑定邮箱验证码成功", r.json()["code"] == 0, r.json().get("msg", ""))
    r = requests.post(f"{BASE}/auth/bind-email", json={"email": bind_email_addr, "code": code}, timeout=10)
    check("未登录绑定邮箱 401", r.status_code == 401)
    r = requests.post(f"{BASE}/auth/bind-email", json={"email": "not-an-email", "code": code}, cookies=user_ck, timeout=10)
    check("绑定非法格式邮箱被拒", r.json()["code"] == 1)
    r = requests.post(f"{BASE}/auth/bind-email", json={"email": email, "code": code}, cookies=user_ck, timeout=10)
    check("绑定他人已占用邮箱被拒", r.json()["code"] == 1)
    r = requests.post(f"{BASE}/auth/bind-email", json={"email": bind_email_addr, "code": "999999"}, cookies=user_ck, timeout=10)
    check("错误验证码绑定邮箱被拒", r.json()["code"] == 1)
    with Session(engine) as session:
        session.add(
            VerificationCode(
                target=bind_email_addr,
                channel="email",
                purpose="bind_email",
                code_hash=sha256_text(code),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            )
        )
        session.commit()
    r = requests.post(f"{BASE}/auth/bind-email", json={"email": bind_email_addr, "code": code}, cookies=user_ck, timeout=10)
    body = r.json()
    check("短信用户绑定邮箱成功", body["code"] == 0 and body["data"]["email"] == bind_email_addr)
    r = requests.post(
        f"{BASE}/auth/login",
        json={"account": bind_email_addr, "password": "user-pass-1", "device_id": user_device},
        timeout=10,
    )
    check("绑定后可用邮箱登录", r.json()["code"] == 0)

    # 17. 未登录访问资源列表 -> 401
    r = requests.get(f"{BASE}/resources", timeout=10)
    check("未登录访问被拒绝", r.status_code == 401)

    # 18. 普通用户资源列表（不返回网盘链接）
    r = requests.get(f"{BASE}/resources", cookies=user_ck, timeout=10)
    body = r.json()
    check("用户获取资源列表", body["code"] == 0 and len(body["data"]) >= 1)
    target_item = next((x for x in body["data"] if x["id"] == resource_id), None)
    check("目标资源在列表中", target_item is not None)
    check("列表未泄露网盘链接", target_item is not None and "pan_url" not in target_item)

    # 19. 错误资源块密码解锁失败
    r = requests.post(
        f"{BASE}/resources/{resource_id}/unlock",
        json={"block_password": "bad-password"},
        cookies=user_ck,
        timeout=10,
    )
    check("错误资源块密码解锁失败", r.json()["code"] == 1)

    # 20. 正确密码解锁成功，返回网盘链接
    r = requests.post(
        f"{BASE}/resources/{resource_id}/unlock",
        json={"block_password": block_password},
        cookies=user_ck,
        timeout=10,
    )
    body = r.json()
    check("正确资源块密码解锁成功", body["code"] == 0 and body["data"]["pan_url"] == payload["pan_url"])

    # 20b. 解锁成功后，资源列表中该资源应标记 unlocked=true
    r = requests.get(f"{BASE}/resources", cookies=user_ck, timeout=10)
    body = r.json()
    target_item = next((x for x in body["data"] if x["id"] == resource_id), None)
    check("解锁后列表标记 unlocked", target_item is not None and target_item.get("unlocked") is True)

    # 20c. 免密直显：空密码再次解锁，直接返回网盘链接
    r = requests.post(
        f"{BASE}/resources/{resource_id}/unlock",
        json={"block_password": ""},
        cookies=user_ck,
        timeout=10,
    )
    body = r.json()
    check("历史解锁后空密码直显网盘链接", body["code"] == 0 and body["data"]["pan_url"] == payload["pan_url"])

    # 20d. 未解锁过的资源空密码调用应失败
    r = requests.post(
        f"{BASE}/admin/resources",
        json={**payload, "name": "smoke-未解锁资源"},
        cookies=admin_ck,
        timeout=10,
    )
    locked_id = r.json()["data"]["id"]
    r = requests.post(
        f"{BASE}/resources/{locked_id}/unlock",
        json={"block_password": ""},
        cookies=user_ck,
        timeout=10,
    )
    check("未解锁资源空密码被拒绝", r.json()["code"] == 1)
    requests.delete(f"{BASE}/admin/resources/{locked_id}", cookies=admin_ck, timeout=10)

    # 21. 权限：普通用户不能访问管理接口
    r = requests.get(f"{BASE}/admin/resources", cookies=user_ck, timeout=10)
    check("普通用户访问管理接口 403", r.status_code == 403)

    # 22. 管理员访问记录包含成功/失败两条
    r = requests.get(f"{BASE}/admin/logs", cookies=admin_ck, timeout=10)
    body = r.json()
    check("管理员查看访问记录", body["code"] == 0 and len(body["data"]) >= 2)
    check("记录含成功与失败", any(x["success"] for x in body["data"]) and any(not x["success"] for x in body["data"]))

    # 23. 管理员更新站点配置
    r = requests.put(
        f"{BASE}/admin/config",
        json={"site_name": "SourceLink 冒烟测试站点"},
        cookies=admin_ck,
        timeout=10,
    )
    check("更新站点配置成功", r.json()["code"] == 0)
    r = requests.get(f"{BASE}/config/public", timeout=10)
    check("公开配置已同步", r.json()["data"]["site_name"] == "SourceLink 冒烟测试站点")
    # 还原
    requests.put(f"{BASE}/admin/config", json={"site_name": "SourceLink 资源托管平台"}, cookies=admin_ck, timeout=10)

    # 23b. 会话空闲时长配置：管理员修改后新签发令牌有效期同步变化
    r = requests.put(f"{BASE}/admin/config", json={"session_idle_minutes": "abc"}, cookies=admin_ck, timeout=10)
    check("空闲时长非法值被拒", r.json()["code"] == 1)
    r = requests.put(f"{BASE}/admin/config", json={"session_idle_minutes": "1"}, cookies=admin_ck, timeout=10)
    check("空闲时长低于下限被拒", r.json()["code"] == 1)
    r = requests.put(f"{BASE}/admin/config", json={"session_idle_minutes": "30"}, cookies=admin_ck, timeout=10)
    body = r.json()
    check("修改会话空闲时长成功", body["code"] == 0 and body["data"]["session_idle_minutes"] == "30")
    r = requests.post(
        f"{BASE}/auth/login",
        json={"account": "admin", "password": "1q2w3e4r", "device_id": admin_device},
        timeout=10,
    )
    check("重新登录成功", r.json()["code"] == 0)
    # 校验新会话有效期按配置 30 分钟签发（服务端会话表 expires_at - last_active_at）
    with Session(engine) as session:
        row = session.exec(select(UserSession).order_by(UserSession.id.desc())).first()
    check(
        "新会话有效期按配置 30 分钟签发",
        row is not None and abs((row.expires_at - row.last_active_at).total_seconds() - 30 * 60) < 5,
    )
    # 还原为 60，保证后续续期阈值检查（55 分钟不续期）成立
    requests.put(f"{BASE}/admin/config", json={"session_idle_minutes": "60"}, cookies=admin_ck, timeout=10)

    # 24. 删除资源块
    r = requests.delete(f"{BASE}/admin/resources/{delete_id}", cookies=admin_ck, timeout=10)
    check("删除资源块成功", r.json()["code"] == 0)
    r = requests.delete(f"{BASE}/admin/resources/{delete_id}", cookies=admin_ck, timeout=10)
    check("重复删除返回错误", r.json()["code"] == 1)

    # 25. 用户反馈：普通用户提交并只看到自己的
    r = requests.post(f"{BASE}/feedback", json={"content": "冒烟测试用户反馈"}, cookies=user_ck, timeout=10)
    check("用户提交反馈成功", r.json()["code"] == 0)
    r = requests.post(f"{BASE}/feedback", json={"content": "管理员测试反馈"}, cookies=admin_ck, timeout=10)
    check("管理员提交反馈成功", r.json()["code"] == 0)
    r = requests.get(f"{BASE}/feedback", cookies=user_ck, timeout=10)
    body = r.json()
    check("普通用户仅看到自己的反馈", body["code"] == 0 and all(x["content"] == "冒烟测试用户反馈" for x in body["data"]))
    r = requests.get(f"{BASE}/feedback", cookies=admin_ck, timeout=10)
    body = r.json()
    contents = {x["content"] for x in body["data"]}
    check("管理员看到全部反馈", body["code"] == 0 and "冒烟测试用户反馈" in contents and "管理员测试反馈" in contents)
    check("管理员反馈带提交者账号", all(x.get("account") for x in body["data"]))
    r = requests.post(f"{BASE}/feedback", json={"content": ""}, cookies=user_ck, timeout=10)
    check("空反馈被拒绝", r.json()["code"] == 1)
    r = requests.get(f"{BASE}/feedback", timeout=10)
    check("未登录查看反馈被拒", r.status_code == 401)

    # 25b. 管理员删除反馈：单条删除 + 全量删除（仅管理员）
    r = requests.get(f"{BASE}/feedback", cookies=admin_ck, timeout=10)
    fb_ids = [x["id"] for x in r.json()["data"]]
    check("删除前至少两条反馈", len(fb_ids) >= 2)
    r = requests.delete(f"{BASE}/feedback/{fb_ids[0]}", cookies=user_ck, timeout=10)
    check("普通用户删除反馈 403", r.status_code == 403)
    r = requests.delete(f"{BASE}/feedback/{fb_ids[0]}", cookies=admin_ck, timeout=10)
    check("管理员单条删除反馈成功", r.json()["code"] == 0)
    r = requests.delete(f"{BASE}/feedback/{fb_ids[0]}", cookies=admin_ck, timeout=10)
    check("重复删除反馈返回错误", r.json()["code"] == 1)
    r = requests.delete(f"{BASE}/feedback", cookies=user_ck, timeout=10)
    check("普通用户清空反馈 403", r.status_code == 403)
    r = requests.delete(f"{BASE}/feedback", cookies=admin_ck, timeout=10)
    check("管理员清空反馈成功", r.json()["code"] == 0 and r.json()["data"]["deleted"] >= 1)
    r = requests.get(f"{BASE}/feedback", cookies=admin_ck, timeout=10)
    check("清空后反馈列表为空", r.json()["code"] == 0 and len(r.json()["data"]) == 0)

    # 22b. 管理员删除访问记录：单条删除 + 全量删除（仅管理员）
    r = requests.get(f"{BASE}/admin/logs", cookies=admin_ck, timeout=10)
    log_ids = [x["id"] for x in r.json()["data"]]
    check("删除前存在访问记录", len(log_ids) >= 1)
    r = requests.delete(f"{BASE}/admin/logs/{log_ids[0]}", cookies=user_ck, timeout=10)
    check("普通用户删除访问记录 403", r.status_code == 403)
    r = requests.delete(f"{BASE}/admin/logs/{log_ids[0]}", cookies=admin_ck, timeout=10)
    check("管理员单条删除访问记录成功", r.json()["code"] == 0)
    r = requests.delete(f"{BASE}/admin/logs/{log_ids[0]}", cookies=admin_ck, timeout=10)
    check("重复删除访问记录返回错误", r.json()["code"] == 1)
    r = requests.delete(f"{BASE}/admin/logs", cookies=user_ck, timeout=10)
    check("普通用户清空访问记录 403", r.status_code == 403)
    r = requests.delete(f"{BASE}/admin/logs", cookies=admin_ck, timeout=10)
    check("管理员清空访问记录成功", r.json()["code"] == 0)
    r = requests.get(f"{BASE}/admin/logs", cookies=admin_ck, timeout=10)
    check("清空后访问记录为空", r.json()["code"] == 0 and len(r.json()["data"]) == 0)

    # 26. Cookie 会话空闲续期：剩余不足一半有效期的会话请求后自动滑动续期并刷新 Cookie
    now = datetime.now(timezone.utc)
    short_tok = f"smoke-short-{suffix}"
    long_tok = f"smoke-long-{suffix}"
    expired_tok = f"smoke-expired-{suffix}"
    with Session(engine) as session:
        session.add(UserSession(
            token=short_tok,
            user_id=1,
            created_at=now - timedelta(minutes=50),
            last_active_at=now - timedelta(minutes=50),
            expires_at=now + timedelta(minutes=10),
        ))
        session.add(UserSession(
            token=long_tok,
            user_id=1,
            created_at=now,
            last_active_at=now,
            expires_at=now + timedelta(minutes=55),
        ))
        session.add(UserSession(
            token=expired_tok,
            user_id=1,
            created_at=now - timedelta(hours=3),
            last_active_at=now - timedelta(hours=2),
            expires_at=now - timedelta(minutes=10),
        ))
        session.commit()

    r = requests.get(f"{BASE}/auth/me", cookies={"sl_session": short_tok}, timeout=10)
    check("快过期会话触发续期（重新下发 Cookie）", r.status_code == 200 and "sl_session" in r.headers.get("set-cookie", ""))
    with Session(engine) as session:
        row = session.exec(select(UserSession).where(UserSession.token == short_tok)).first()
    check("续期后服务端有效期已延长", row is not None and (row.expires_at - datetime.now(timezone.utc)).total_seconds() > 55 * 60)

    r = requests.get(f"{BASE}/auth/me", cookies={"sl_session": long_tok}, timeout=10)
    check("剩余充足时不重复续期", r.status_code == 200 and "sl_session" not in r.headers.get("set-cookie", ""))
    r = requests.get(f"{BASE}/auth/me", cookies={"sl_session": expired_tok}, timeout=10)
    check("过期会话 401 需重新登录", r.status_code == 401)
    r = requests.get(f"{BASE}/auth/me", cookies={"sl_session": "not-exist-token"}, timeout=10)
    check("非法会话标识 401", r.status_code == 401)

    # 27. 管理员用户管理：新建 / 查看 / 编辑 / 删除客户账户（需求 2）
    r = requests.get(f"{BASE}/admin/users", cookies=user_ck, timeout=10)
    check("普通用户访问用户管理 403", r.status_code == 403)
    mgmt_username = f"smoke{suffix}"
    r = requests.post(f"{BASE}/admin/users", json={"password": "123456"}, cookies=admin_ck, timeout=10)
    check("新建用户缺少登录账号被拒", r.json()["code"] == 1)
    r = requests.post(
        f"{BASE}/admin/users",
        json={"username": mgmt_username, "password": "mgmt-pass-1"},
        cookies=admin_ck,
        timeout=10,
    )
    body = r.json()
    check("管理员新建用户成功", body["code"] == 0 and body["data"]["username"] == mgmt_username)
    mgmt_id = body["data"]["id"]
    r = requests.post(
        f"{BASE}/admin/users",
        json={"username": mgmt_username, "password": "mgmt-pass-1"},
        cookies=admin_ck,
        timeout=10,
    )
    check("重复用户名新建被拒", r.json()["code"] == 1)
    r = requests.get(f"{BASE}/admin/users", params={"keyword": mgmt_username}, cookies=admin_ck, timeout=10)
    body = r.json()
    check("用户管理列表可查到新用户", body["code"] == 0 and any(x["id"] == mgmt_id for x in body["data"]))

    # 新设备首次登录需滑动验证
    mgmt_device = f"smoke-mgmt-device-{suffix}"
    r = requests.post(
        f"{BASE}/auth/login",
        json={"account": mgmt_username, "password": "mgmt-pass-1", "device_id": mgmt_device},
        timeout=10,
    )
    check("新建用户登录触发新设备滑动验证", r.json()["code"] == 4011)
    mgmt_ticket = solve_captcha()
    r = requests.post(
        f"{BASE}/auth/login",
        json={"account": mgmt_username, "password": "mgmt-pass-1", "device_id": mgmt_device, "captcha_ticket": mgmt_ticket},
        timeout=10,
    )
    check("新建用户滑动验证后登录成功", r.json()["code"] == 0)
    mgmt_ck = {"sl_session": r.cookies.get("sl_session")}

    r = requests.put(
        f"{BASE}/admin/users/{mgmt_id}",
        json={"phone": "137" + suffix, "password": "mgmt-pass-2"},
        cookies=admin_ck,
        timeout=10,
    )
    check("管理员编辑用户（绑定手机号+重置密码）成功", r.json()["code"] == 0)
    r = requests.get(f"{BASE}/auth/me", cookies=mgmt_ck, timeout=10)
    check("重置密码后旧会话被强制下线", r.status_code == 401)
    r = requests.post(
        f"{BASE}/auth/login",
        json={"account": "137" + suffix, "password": "mgmt-pass-2", "device_id": mgmt_device},
        timeout=10,
    )
    check("重置后可用新手机号+新密码登录", r.json()["code"] == 0)

    r = requests.put(f"{BASE}/admin/users/{mgmt_id}", json={"is_active": False}, cookies=admin_ck, timeout=10)
    check("管理员停用用户成功", r.json()["code"] == 0 and r.json()["data"]["is_active"] is False)
    r = requests.post(
        f"{BASE}/auth/login",
        json={"account": mgmt_username, "password": "mgmt-pass-2", "device_id": mgmt_device},
        timeout=10,
    )
    check("停用用户登录被拒", r.status_code == 401)
    r = requests.put(f"{BASE}/admin/users/1", json={"is_active": False}, cookies=admin_ck, timeout=10)
    check("编辑管理员账户被拒", r.json()["code"] == 1)
    r = requests.delete(f"{BASE}/admin/users/1", cookies=admin_ck, timeout=10)
    check("删除管理员账户被拒", r.json()["code"] == 1)
    r = requests.delete(f"{BASE}/admin/users/{mgmt_id}", cookies=admin_ck, timeout=10)
    check("管理员删除用户成功", r.json()["code"] == 0)
    r = requests.post(
        f"{BASE}/auth/login",
        json={"account": mgmt_username, "password": "mgmt-pass-2", "device_id": mgmt_device},
        timeout=10,
    )
    check("已删除用户登录 401", r.status_code == 401)

    # 28. 忘记密码：邮箱验证码重置（需求 4）
    r = requests.post(
        f"{BASE}/verification/send",
        json={"target": f"nobody{suffix}@example.com", "channel": "email", "purpose": "reset_password"},
        timeout=10,
    )
    check("未注册邮箱发送重置验证码被拒", r.json()["code"] == 1)
    r = requests.post(
        f"{BASE}/verification/send",
        json={"target": email, "channel": "email", "purpose": "reset_password"},
        timeout=10,
    )
    check("已注册邮箱发送重置验证码成功", r.json()["code"] == 0, r.json().get("msg", ""))
    reset_code = "654321"
    with Session(engine) as session:
        session.add(
            VerificationCode(
                target=email,
                channel="email",
                purpose="reset_password",
                code_hash=sha256_text(reset_code),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            )
        )
        session.commit()
    r = requests.post(
        f"{BASE}/auth/forgot-password",
        json={"email": email, "code": "000000", "password": "reset-pass-9"},
        timeout=10,
    )
    check("错误重置验证码被拒", r.json()["code"] == 1)
    r = requests.post(
        f"{BASE}/auth/forgot-password",
        json={"email": email, "code": reset_code, "password": "reset-pass-9"},
        timeout=10,
    )
    check("忘记密码重置成功", r.json()["code"] == 0, r.json().get("msg", ""))
    r = requests.get(f"{BASE}/auth/me", cookies=email_ck, timeout=10)
    check("重置密码后原会话被强制下线", r.status_code == 401)
    r = requests.post(
        f"{BASE}/auth/login",
        json={"account": email, "password": "user-pass-1", "device_id": user_device},
        timeout=10,
    )
    check("旧密码登录失败", r.status_code == 401)
    r = requests.post(
        f"{BASE}/auth/login",
        json={"account": email, "password": "reset-pass-9", "device_id": user_device},
        timeout=10,
    )
    body = r.json()
    check("新密码登录成功", body["code"] == 0)
    email_ck = {"sl_session": r.cookies.get("sl_session")}

    # 29. 退出登录：删除服务端会话并使 Cookie 失效
    r = requests.post(f"{BASE}/auth/logout", cookies=email_ck, timeout=10)
    check("退出登录成功", r.json()["code"] == 0)
    r = requests.get(f"{BASE}/auth/me", cookies=email_ck, timeout=10)
    check("退出后原会话 Cookie 失效 401", r.status_code == 401)

    print(f"\n全部通过，共 {passed} 项检查。")


if __name__ == "__main__":
    main()
