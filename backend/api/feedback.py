"""用户反馈接口：提交反馈、按角色查看。"""

from flask import Blueprint, g
from sqlmodel import Session

from ..database import engine
from ..services import feedback as feedback_service
from .common import fail, get_json, ok, require_auth

bp = Blueprint("feedback", __name__)


@bp.post("/feedback")
@require_auth()
def create_feedback():
    try:
        item = feedback_service.create_feedback(g.session, g.user, get_json().get("content", ""))
    except feedback_service.FeedbackError as exc:
        return fail(str(exc))
    return ok({"id": item.id}, "反馈已提交")


@bp.get("/feedback")
@require_auth()
def list_feedback():
    return ok(feedback_service.list_feedback(g.session, g.user))


@bp.delete("/feedback/<int:feedback_id>")
@require_auth(admin=True)
def delete_feedback(feedback_id: int):
    try:
        feedback_service.delete_feedback(g.session, feedback_id)
    except feedback_service.FeedbackError as exc:
        return fail(str(exc))
    return ok(msg="删除成功")


@bp.delete("/feedback")
@require_auth(admin=True)
def delete_all_feedback():
    count = feedback_service.delete_all_feedback(g.session)
    return ok({"deleted": count}, f"已清空 {count} 条反馈")
