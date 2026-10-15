"""SQLModel 数据库引擎与会话管理。"""

from sqlmodel import SQLModel, Session, create_engine

from .config import Config

engine = create_engine(
    Config.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    """建表（导入模型以注册表元数据）。"""
    Config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # noqa: F401  导入即注册模型
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI 风格的会话依赖，Flask 中直接在视图里取用。"""
    with Session(engine) as session:
        yield session
