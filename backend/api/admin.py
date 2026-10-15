"""管理后台接口：资源块 CRUD、站点配置、访问记录、用户管理。"""

from flask import Blueprint, g, request

from ..services import auth as auth_service
from ..services import resource as resource_service
from ..services import site_config
from .common import fail, get_json, ok, require_auth

bp = Blueprint("admin", __name__)


# ---------------- 资源块管理 ----------------

@bp.get("/admin/resources")
@require_auth(admin=True)
def list_resources():
    resources = resource_service.list_all(g.session)
    return ok([resource_service.serialize(item, reveal=True) for item in resources])


@bp.post("/admin/resources")
@require_auth(admin=True)
def create_resource():
    try:
        resource = resource_service.create_resource(g.session, get_json())
    except resource_service.ResourceError as exc:
        return fail(str(exc))
    return ok(resource_service.serialize(resource, reveal=True), "创建成功")


@bp.put("/admin/resources/<int:resource_id>")
@require_auth(admin=True)
def update_resource(resource_id: int):
    try:
        resource = resource_service.update_resource(g.session, resource_id, get_json())
    except resource_service.ResourceError as exc:
        return fail(str(exc))
    return ok(resource_service.serialize(resource, reveal=True), "更新成功")


@bp.delete("/admin/resources/<int:resource_id>")
@require_auth(admin=True)
def delete_resource(resource_id: int):
    try:
        resource_service.delete_resource(g.session, resource_id)
    except resource_service.ResourceError as exc:
        return fail(str(exc))
    return ok(msg="删除成功")


# ---------------- 站点配置 ----------------

@bp.get("/admin/config")
@require_auth(admin=True)
def get_config():
    return ok(site_config.all_config())


@bp.put("/admin/config")
@require_auth(admin=True)
def update_config():
    data = get_json()
    if not isinstance(data, dict) or not data:
        return fail("配置内容不能为空")
    # 会话空闲失效时长：5 分钟 ~ 7 天的整数
    if "session_idle_minutes" in data:
        try:
            idle = int(str(data["session_idle_minutes"]).strip())
        except (TypeError, ValueError):
            return fail("会话空闲失效时长必须为整数分钟")
        if not site_config.SESSION_IDLE_MIN <= idle <= site_config.SESSION_IDLE_MAX:
            return fail(
                f"会话空闲失效时长需在 {site_config.SESSION_IDLE_MIN}-{site_config.SESSION_IDLE_MAX} 分钟之间"
            )
        data["session_idle_minutes"] = str(idle)
    # 资源有效期：月/天/小时必须为非负整数，且三项不能同时为 0（0 表示永久有效，允许）
    for key, max_val, label in (
        ("resource_ttl_months", site_config.RESOURCE_TTL_MONTHS_MAX, "月"),
        ("resource_ttl_days", site_config.RESOURCE_TTL_DAYS_MAX, "天"),
        ("resource_ttl_hours", site_config.RESOURCE_TTL_HOURS_MAX, "小时"),
    ):
        if key in data:
            try:
                value = int(str(data[key]).strip())
            except (TypeError, ValueError):
                return fail(f"资源有效期{label}必须为非负整数")
            if value < 0 or value > max_val:
                return fail(f"资源有效期{label}需在 0-{max_val} 之间")
            data[key] = str(value)
    config = site_config.update_config(g.session, data)
    return ok(config, "配置已保存")


# ---------------- 用户管理（新建 / 查看 / 编辑 / 删除客户账户） ----------------

@bp.get("/admin/users")
@require_auth(admin=True)
def list_users():
    return ok(auth_service.admin_list_users(g.session, request.args.get("keyword", "")))


@bp.post("/admin/users")
@require_auth(admin=True)
def create_user():
    try:
        user = auth_service.admin_create_user(g.session, get_json())
    except auth_service.AuthError as exc:
        return fail(str(exc))
    return ok(auth_service.serialize_user(user), "创建成功")


@bp.put("/admin/users/<int:user_id>")
@require_auth(admin=True)
def update_user(user_id: int):
    try:
        user = auth_service.admin_update_user(g.session, user_id, get_json())
    except auth_service.AuthError as exc:
        return fail(str(exc))
    return ok(auth_service.serialize_user(user), "更新成功")


@bp.delete("/admin/users/<int:user_id>")
@require_auth(admin=True)
def delete_user(user_id: int):
    try:
        auth_service.admin_delete_user(g.session, user_id)
    except auth_service.AuthError as exc:
        return fail(str(exc))
    return ok(msg="删除成功")


# ---------------- 访问记录 ----------------

@bp.get("/admin/logs")
@require_auth(admin=True)
def access_logs():
    return ok(resource_service.list_access_logs(g.session))


@bp.delete("/admin/logs/<int:log_id>")
@require_auth(admin=True)
def delete_access_log(log_id: int):
    try:
        resource_service.delete_access_log(g.session, log_id)
    except resource_service.ResourceError as exc:
        return fail(str(exc))
    return ok(msg="删除成功")


@bp.delete("/admin/logs")
@require_auth(admin=True)
def clear_access_logs():
    count = resource_service.clear_access_logs(g.session)
    return ok({"deleted": count}, f"已清空 {count} 条访问记录")
