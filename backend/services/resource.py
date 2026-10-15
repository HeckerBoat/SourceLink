"""资源块业务：管理员 CRUD 与用户解锁查看。"""

from datetime import datetime, timezone

from sqlmodel import Session, select

from ..models import AccessLog, ResourceBlock, User
from .security import hash_password, verify_password
from . import site_config


class ResourceError(Exception):
    """资源块业务异常。"""


REQUIRED_FIELDS = ("name", "pan_url", "purchase_url", "block_password")


def _validate_payload(data: dict, partial: bool = False) -> None:
    if not partial:
        for field in REQUIRED_FIELDS:
            if not str(data.get(field, "")).strip():
                raise ResourceError(f"缺少必填字段: {field}")
    name = data.get("name")
    if name is not None and not str(name).strip():
        raise ResourceError("资源名称不能为空")
    for url_field in ("pan_url", "purchase_url"):
        value = data.get(url_field)
        if value is not None:
            value = str(value).strip()
            if not value.startswith(("http://", "https://")):
                raise ResourceError(f"{url_field} 必须以 http:// 或 https:// 开头")


def serialize(resource: ResourceBlock, *, reveal: bool = False, unlocked: bool = False) -> dict:
    expired = site_config.is_resource_expired(resource.created_at)
    data = {
        "id": resource.id,
        "name": resource.name,
        "description": resource.description or "",
        "purchase_url": resource.purchase_url,
        "is_published": resource.is_published,
        "expired": expired,
        "unlocked": unlocked,
        "created_at": resource.created_at.isoformat() if resource.created_at else None,
        "updated_at": resource.updated_at.isoformat() if resource.updated_at else None,
    }
    # 网盘链接仅在解锁/管理员场景返回；密码哈希任何时候都不返回
    if reveal:
        data["pan_url"] = resource.pan_url
    return data


def unlocked_ids(session: Session, user_id: int) -> set[int]:
    """当前用户曾经成功解锁过的资源块 ID 集合（用于“解锁过一次即直接展示”）。"""
    rows = session.exec(
        select(AccessLog.resource_id).where(
            AccessLog.user_id == user_id,
            AccessLog.success == True,  # noqa: E712
        )
    ).all()
    return set(rows)


def has_unlocked(session: Session, user_id: int, resource_id: int) -> bool:
    return resource_id in unlocked_ids(session, user_id)


def _auto_unpublish_expired(session: Session, resources: list[ResourceBlock]) -> None:
    """把已过期的资源自动下架（仅修改未下架的过期资源）。"""
    changed = False
    for resource in resources:
        if resource.is_published and site_config.is_resource_expired(resource.created_at):
            resource.is_published = False
            resource.updated_at = datetime.now(timezone.utc)
            session.add(resource)
            changed = True
    if changed:
        session.commit()


def list_published(session: Session) -> list[ResourceBlock]:
    """普通用户可见的资源列表：未过期且已上架。"""
    resources = list(
        session.exec(
            select(ResourceBlock)
            .where(ResourceBlock.is_published == True)  # noqa: E712
            .order_by(ResourceBlock.created_at.desc())
        ).all()
    )
    _auto_unpublish_expired(session, resources)
    return [r for r in resources if not site_config.is_resource_expired(r.created_at)]


def list_all(session: Session) -> list[ResourceBlock]:
    """管理员可见的全部资源列表，返回前先把过期资源自动下架。"""
    resources = list(session.exec(select(ResourceBlock).order_by(ResourceBlock.created_at.desc())).all())
    _auto_unpublish_expired(session, resources)
    return resources


def get(session: Session, resource_id: int) -> ResourceBlock:
    resource = session.get(ResourceBlock, resource_id)
    if resource is None:
        raise ResourceError("资源块不存在")
    return resource


def create_resource(session: Session, data: dict) -> ResourceBlock:
    _validate_payload(data)
    resource = ResourceBlock(
        name=str(data["name"]).strip(),
        description=(data.get("description") or "").strip() or None,
        pan_url=str(data["pan_url"]).strip(),
        purchase_url=str(data["purchase_url"]).strip(),
        block_password_hash=hash_password(str(data["block_password"])),
        is_published=bool(data.get("is_published", True)),
    )
    session.add(resource)
    session.commit()
    session.refresh(resource)
    return resource


def update_resource(session: Session, resource_id: int, data: dict) -> ResourceBlock:
    resource = get(session, resource_id)
    _validate_payload(data, partial=True)

    if "name" in data:
        resource.name = str(data["name"]).strip()
    if "description" in data:
        resource.description = (str(data.get("description") or "")).strip() or None
    if "pan_url" in data:
        resource.pan_url = str(data["pan_url"]).strip()
    if "purchase_url" in data:
        resource.purchase_url = str(data["purchase_url"]).strip()
    if "is_published" in data:
        new_state = bool(data["is_published"])
        if new_state and site_config.is_resource_expired(resource.created_at):
            raise ResourceError("资源已过期，无法上架")
        resource.is_published = new_state
    new_password = data.get("block_password")
    if new_password:
        resource.block_password_hash = hash_password(str(new_password))
    resource.updated_at = datetime.now(timezone.utc)

    session.add(resource)
    session.commit()
    session.refresh(resource)
    return resource


def delete_resource(session: Session, resource_id: int) -> None:
    resource = get(session, resource_id)
    session.delete(resource)
    session.commit()


def unlock(session: Session, user: User, resource_id: int, password: str) -> ResourceBlock:
    """校验资源块密码，记录访问日志（成功/失败均记录），成功时返回资源块。

    需求规则：用户曾经成功解锁过该资源块后，再次查看无需重复输入密码，
    此时前端以空密码调用，命中历史成功记录即直接放行（不重复写日志）。
    """
    resource = session.get(ResourceBlock, resource_id)

    # 过期资源禁止解锁（无论是否输入密码）
    if resource and site_config.is_resource_expired(resource.created_at):
        raise ResourceError("资源已过期，无法查看")

    # 免密直显：历史上已成功解锁过，直接返回
    if not password:
        if resource and resource.is_published and has_unlocked(session, user.id, resource_id):
            return resource
        raise ResourceError("请输入资源块密码")

    success = bool(resource and resource.is_published and verify_password(password, resource.block_password_hash))
    session.add(
        AccessLog(user_id=user.id, resource_id=resource_id, success=success)
    )
    session.commit()
    if not success:
        raise ResourceError("资源块密码错误")
    return resource


def delete_access_log(session: Session, log_id: int) -> None:
    """删除单条访问记录。"""
    log = session.get(AccessLog, log_id)
    if log is None:
        raise ResourceError("访问记录不存在")
    session.delete(log)
    session.commit()


def clear_access_logs(session: Session) -> int:
    """清空全部访问记录，返回删除条数。"""
    logs = session.exec(select(AccessLog)).all()
    count = len(logs)
    for log in logs:
        session.delete(log)
    session.commit()
    return count


def list_access_logs(session: Session, limit: int = 100) -> list[dict]:
    """管理端访问记录（联表带出用户名/资源名）。"""
    users = {u.id: u for u in session.exec(select(User)).all()}
    resources = {r.id: r for r in session.exec(select(ResourceBlock)).all()}
    logs = session.exec(
        select(AccessLog).order_by(AccessLog.created_at.desc()).limit(limit)
    ).all()
    result = []
    for log in logs:
        user = users.get(log.user_id)
        resource = resources.get(log.resource_id)
        result.append(
            {
                "id": log.id,
                "user_account": (user.username or user.phone or user.email) if user else f"#{log.user_id}",
                "resource_name": resource.name if resource else f"#{log.resource_id}",
                "success": log.success,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
        )
    return result
