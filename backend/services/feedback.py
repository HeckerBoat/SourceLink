"""用户反馈业务：提交、按角色查询。"""

from datetime import datetime, timezone

from sqlmodel import Session, select

from ..models import Feedback, User


class FeedbackError(Exception):
    """反馈业务异常，消息可直接返回给前端。"""


MAX_CONTENT = 2000


def create_feedback(session: Session, user: User, content: str) -> Feedback:
    content = (content or "").strip()
    if not content:
        raise FeedbackError("反馈内容不能为空")
    if len(content) > MAX_CONTENT:
        raise FeedbackError(f"反馈内容不能超过 {MAX_CONTENT} 字")
    item = Feedback(user_id=user.id, content=content, created_at=datetime.now(timezone.utc))
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def _serialize(item: Feedback, user: User | None) -> dict:
    account = ""
    if user is not None:
        account = user.username or user.phone or user.email or f"用户#{item.user_id}"
    return {
        "id": item.id,
        "user_id": item.user_id,
        "account": account,
        "content": item.content,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def delete_feedback(session: Session, feedback_id: int) -> None:
    """删除单条反馈（仅管理员，由接口层鉴权）。"""
    item = session.get(Feedback, feedback_id)
    if item is None:
        raise FeedbackError("反馈不存在")
    session.delete(item)
    session.commit()


def delete_all_feedback(session: Session) -> int:
    """清空全部反馈，返回删除条数（仅管理员，由接口层鉴权）。"""
    items = session.exec(select(Feedback)).all()
    count = len(items)
    for item in items:
        session.delete(item)
    session.commit()
    return count


def list_feedback(session: Session, user: User) -> list[dict]:
    """管理员返回全部反馈（附提交者账号），普通用户仅返回自己的。"""
    query = select(Feedback).order_by(Feedback.created_at.desc())
    if not user.is_admin:
        query = query.where(Feedback.user_id == user.id)
    items = session.exec(query).all()

    if user.is_admin:
        users = {u.id: u for u in session.exec(select(User)).all()}
        return [_serialize(item, users.get(item.user_id)) for item in items]
    return [_serialize(item, user) for item in items]
