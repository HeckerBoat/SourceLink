"""资源有效期与过期自动下架专项测试（需先启动 app.py）。

运行：
    .\\.venv\\Scripts\\python.exe test\\ttl_test.py
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select  # noqa: E402

from backend.config import Config  # noqa: E402
from backend.database import engine  # noqa: E402
from backend.models import ResourceBlock, SiteConfig  # noqa: E402
from backend.services import site_config  # noqa: E402

passed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" -> {detail}" if detail else ""))
    if not condition:
        raise AssertionError(name)
    passed += 1


def _set_ttl(months: int, days: int, hours: int) -> None:
    with Session(engine) as session:
        site_config.load_to_cache(session)
        site_config.update_config(session, {
            "resource_ttl_months": str(months),
            "resource_ttl_days": str(days),
            "resource_ttl_hours": str(hours),
        })


def _cleanup() -> None:
    with Session(engine) as session:
        stale = session.exec(
            select(ResourceBlock).where(ResourceBlock.name.like("TTL测试%"))
        ).all()
        for item in stale:
            session.delete(item)
        session.commit()


def main() -> None:
    _cleanup()
    _set_ttl(0, 0, 0)

    # 1. 永久有效判定
    with Session(engine) as session:
        site_config.load_to_cache(session)
        r = ResourceBlock(
            name="TTL测试永久",
            pan_url="https://pan.example.com/forever",
            purchase_url="https://buy.example.com/forever",
            block_password_hash="x",
            is_published=True,
            created_at=datetime.now(timezone.utc) - timedelta(days=365),
        )
        session.add(r)
        session.commit()
        session.refresh(r)
        check("三项全 0 视为永久有效", site_config.is_resource_expired(r.created_at) is False)

    # 2. 过期判定
    _set_ttl(0, 1, 0)  # 1 天有效期
    with Session(engine) as session:
        site_config.load_to_cache(session)
        expired_r = ResourceBlock(
            name="TTL测试已过期",
            pan_url="https://pan.example.com/expired",
            purchase_url="https://buy.example.com/expired",
            block_password_hash="x",
            is_published=True,
            created_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
        fresh_r = ResourceBlock(
            name="TTL测试未过期",
            pan_url="https://pan.example.com/fresh",
            purchase_url="https://buy.example.com/fresh",
            block_password_hash="x",
            is_published=True,
            created_at=datetime.now(timezone.utc),
        )
        session.add(expired_r)
        session.add(fresh_r)
        session.commit()
        session.refresh(expired_r)
        session.refresh(fresh_r)
        check("创建 2 天前 + 有效期 1 天 = 已过期", site_config.is_resource_expired(expired_r.created_at) is True)
        check("刚创建 + 有效期 1 天 = 未过期", site_config.is_resource_expired(fresh_r.created_at) is False)

        # 3. 自动下架
        from backend.services import resource as resource_service
        admin_list = resource_service.list_all(session)
        expired_item = next((i for i in admin_list if i.id == expired_r.id), None)
        fresh_item = next((i for i in admin_list if i.id == fresh_r.id), None)
        check("过期资源被自动下架", expired_item is not None and expired_item.is_published is False)
        check("未过期资源保持上架", fresh_item is not None and fresh_item.is_published is True)

        # 4. 用户列表过滤
        user_list = resource_service.list_published(session)
        check("用户列表不含已过期资源", all(i.id != expired_r.id for i in user_list))
        check("用户列表包含未过期资源", any(i.id == fresh_r.id for i in user_list))

        # 5. 禁止上架过期资源
        try:
            resource_service.update_resource(session, expired_r.id, {"is_published": True})
            check("过期资源上架被后端拒绝", False)
        except resource_service.ResourceError as exc:
            check("过期资源上架被后端拒绝", "已过期" in str(exc) or "无法上架" in str(exc))

        # 6. 禁止解锁过期资源
        from backend.models import User
        user = session.exec(select(User).where(User.is_admin == False)).first()  # noqa: E712
        if user is None:
            user = User(username="ttl_test_user", password_hash="x", is_admin=False, is_active=True)
            session.add(user)
            session.commit()
            session.refresh(user)
        try:
            resource_service.unlock(session, user, expired_r.id, "any")
            check("过期资源解锁被后端拒绝", False)
        except resource_service.ResourceError as exc:
            check("过期资源解锁被后端拒绝", "已过期" in str(exc))

    # 7. 修改有效期后状态实时刷新
    _set_ttl(0, 10, 0)  # 改为 10 天
    with Session(engine) as session:
        site_config.load_to_cache(session)
        r = session.get(ResourceBlock, expired_r.id)
        check("有效期放宽后过期状态实时刷新", site_config.is_resource_expired(r.created_at) is False)

    _set_ttl(0, 0, 0)
    _cleanup()
    print(f"\n全部通过，共 {passed} 项检查。")


if __name__ == "__main__":
    main()
