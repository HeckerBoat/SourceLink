"""滑动拼图验证码：图片生成、坐标校验、一次性凭证签发。

流程：
1. 前端调用 POST /api/captcha/new 获取背景图（含缺口）、滑块图与挑战 ID；
2. 用户拖动滑块对准缺口后，前端提交横坐标 → POST /api/captcha/verify；
3. 容差范围内则签发一次性 ticket，注册 / 新设备登录时携带该凭证，
   服务端消费凭证后放行。

挑战与凭证持久化在 captcha_record 表（带过期时间、一次性消费），
便于服务重启后仍可校验，也便于测试脚本直接查库获取正确坐标。
"""

import base64
import io
import random
import uuid
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFilter
from sqlmodel import Session, select

from ..models import CaptchaRecord

# 画布与拼图块尺寸（前端按 300x150 的逻辑分辨率缩放显示，坐标同比例换算）
BG_W, BG_H = 300, 150
BLOCK = 44          # 拼图方块边长
HALF_ALIGN_RATIO = 0.5  # 需求规定：滑块对齐一半（横坐标偏差不超过目标的一半）即验证成功
CHALLENGE_TTL = 300  # 挑战有效期 5 分钟
TICKET_TTL = 300     # 凭证有效期 5 分钟

_MASK_PAD_L, _MASK_PAD_T = 6, 16
_MASK_W, _MASK_H = BLOCK + 22, BLOCK + 22


class CaptchaError(Exception):
    """验证码业务异常，消息可直接返回给前端。"""


def _puzzle_mask() -> Image.Image:
    """经典拼图块形状模板：圆角方块 + 上凸圆 + 右凸圆。"""
    mask = Image.new("L", (_MASK_W, _MASK_H), 0)
    draw = ImageDraw.Draw(mask)
    left, top = _MASK_PAD_L, _MASK_PAD_T
    draw.rounded_rectangle([left, top, left + BLOCK, top + BLOCK], radius=9, fill=255)
    draw.ellipse(
        [left + BLOCK // 2 - 9, top - 18, left + BLOCK // 2 + 9, top],
        fill=255,
    )
    draw.ellipse(
        [left + BLOCK, top + BLOCK // 2 - 9, left + BLOCK + 18, top + BLOCK // 2 + 9],
        fill=255,
    )
    return mask


def _random_background() -> Image.Image:
    """生成随机渐变 + 几何噪声背景，避免使用外部图片。"""
    top = (random.randint(40, 210), random.randint(40, 210), random.randint(40, 210))
    bottom = (random.randint(40, 210), random.randint(40, 210), random.randint(40, 210))
    img = Image.new("RGB", (BG_W, BG_H))
    draw = ImageDraw.Draw(img)
    for y in range(BG_H):
        ratio = y / (BG_H - 1)
        color = tuple(int(a + (b - a) * ratio) for a, b in zip(top, bottom))
        draw.line([(0, y), (BG_W, y)], fill=color)

    for _ in range(random.randint(5, 9)):
        radius = random.randint(10, 34)
        cx, cy = random.randint(-10, BG_W + 10), random.randint(-10, BG_H + 10)
        outline = tuple(random.randint(60, 255) for _ in range(3))
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], outline=outline, width=3)

    for _ in range(random.randint(3, 6)):
        x1, y1 = random.randint(0, BG_W), random.randint(0, BG_H)
        x2, y2 = random.randint(0, BG_W), random.randint(0, BG_H)
        draw.line([(x1, y1), (x2, y2)], fill=tuple(random.randint(60, 255) for _ in range(3)), width=2)

    return img.filter(ImageFilter.GaussianBlur(0.6))


def _to_data_url(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _purge_expired(session: Session) -> None:
    now = datetime.now(timezone.utc)
    for row in session.exec(select(CaptchaRecord).where(CaptchaRecord.expires_at < now)).all():
        session.delete(row)
    session.commit()


def create_challenge(session: Session) -> dict:
    """生成一题滑动拼图：返回背景图、滑块图（base64）与挑战 ID。"""
    _purge_expired(session)

    background = _random_background().convert("RGBA")
    mask = _puzzle_mask()

    pos_x = random.randint(70, BG_W - _MASK_W - 8)
    pos_y = random.randint(12, BG_H - _MASK_H - 8)

    # 从背景抠出带透明通道的滑块拼图
    region = background.crop((pos_x, pos_y, pos_x + _MASK_W, pos_y + _MASK_H))
    slider = Image.new("RGBA", (_MASK_W, _MASK_H))
    slider.paste(region, (0, 0), mask)

    # 背景缺口处叠加半透明阴影，提示缺口位置
    hole = Image.new("RGBA", background.size)
    hole.paste(Image.new("RGBA", (_MASK_W, _MASK_H), (17, 24, 39, 115)), (pos_x, pos_y), mask)
    background = Image.alpha_composite(background, hole)

    challenge_id = uuid.uuid4().hex
    record = CaptchaRecord(
        token=challenge_id,
        kind="challenge",
        answer_x=pos_x + _MASK_PAD_L,  # 滑块内有效区域（方块）左边缘对应的目标横坐标
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=CHALLENGE_TTL),
    )
    session.add(record)
    session.commit()

    return {
        "challenge_id": challenge_id,
        "background": _to_data_url(background.convert("RGB")),
        "slider": _to_data_url(slider),
        "block_size": BLOCK,
        "slider_y": pos_y,
    }


def verify_challenge(session: Session, challenge_id: str, drag_x: float) -> str:
    """校验拖动横坐标，通过则签发一次性 ticket。"""
    challenge_id = (challenge_id or "").strip()
    record = session.get(CaptchaRecord, challenge_id) if challenge_id else None
    if (
        record is None
        or record.kind != "challenge"
        or record.consumed_at is not None
        or record.expires_at < datetime.now(timezone.utc)
    ):
        raise CaptchaError("滑动验证已过期，请重新验证")

    record.consumed_at = datetime.now(timezone.utc)
    session.add(record)

    # 对齐一半即判定成功：横坐标偏差不超过目标坐标的一半
    answer = float(record.answer_x)
    if abs(float(drag_x) - answer) > answer * HALF_ALIGN_RATIO:
        session.commit()
        raise CaptchaError("未对准缺口，请重试")

    ticket = CaptchaRecord(
        token=uuid.uuid4().hex,
        kind="ticket",
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=TICKET_TTL),
    )
    session.add(ticket)
    session.commit()
    return ticket.token


def consume_ticket(session: Session, ticket: str) -> bool:
    """校验并消费一次性凭证；有效返回 True。"""
    ticket = (ticket or "").strip()
    if not ticket:
        return False
    record = session.get(CaptchaRecord, ticket)
    if (
        record is None
        or record.kind != "ticket"
        or record.consumed_at is not None
        or record.expires_at < datetime.now(timezone.utc)
    ):
        return False
    record.consumed_at = datetime.now(timezone.utc)
    session.add(record)
    session.commit()
    return True
