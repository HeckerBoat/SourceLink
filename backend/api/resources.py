"""资源块接口（普通用户）：列表与解锁查看。"""

from flask import Blueprint, g

from ..services import resource as resource_service
from .common import fail, get_json, ok, require_auth

bp = Blueprint("resources", __name__)


@bp.get("/resources")
@require_auth()
def list_resources():
    resources = resource_service.list_published(g.session)
    done = resource_service.unlocked_ids(g.session, g.user.id)
    return ok([
        resource_service.serialize(item, unlocked=item.id in done) for item in resources
    ])


@bp.post("/resources/<int:resource_id>/unlock")
@require_auth()
def unlock(resource_id: int):
    password = get_json().get("block_password", "")
    try:
        resource = resource_service.unlock(g.session, g.user, resource_id, str(password))
    except resource_service.ResourceError as exc:
        return fail(str(exc))
    return ok(resource_service.serialize(resource, reveal=True), "解锁成功")
