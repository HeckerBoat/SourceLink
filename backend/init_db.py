"""数据库初始化：建表、迁移旧库结构、写入默认站点配置、创建内置管理员账户。"""

from sqlmodel import Session, select

from .config import Config
from .database import engine, init_db
from .models import User
from .services import site_config
from .services.migrate import migrate_db, migrate_env
from .services.security import hash_password, verify_password


def init_and_seed() -> None:
    # 需求 16：修改/覆盖配置或数据库时先迁移旧内容
    migrate_env()   # .env 缺失键按模板补齐（已有值保留）
    init_db()       # create_all 建缺失的表
    migrate_db()    # 已存在的表补齐缺失的列（旧数据保留）
    with Session(engine) as session:
        # 1. 默认站点配置
        site_config.seed_defaults(session)
        site_config.load_to_cache(session)

        # 2. 内置管理员：admin / 1q2w3e4r，绑定手机号 11111111111（需求写死）
        admin = session.exec(
            select(User).where(User.username == Config.ADMIN_USERNAME)
        ).first()
        if admin is None:
            admin = User(
                username=Config.ADMIN_USERNAME,
                phone=Config.ADMIN_PHONE,
                password_hash=hash_password(Config.ADMIN_PASSWORD),
                is_admin=True,
                is_active=True,
            )
            session.add(admin)
            session.commit()
            print(f"[init] 已创建管理员账户: {Config.ADMIN_USERNAME} (手机: {Config.ADMIN_PHONE})")
        else:
            # 确保管理员标记与绑定手机号符合配置
            changed = False
            if not admin.is_admin:
                admin.is_admin = True
                changed = True
            if Config.ADMIN_PHONE and admin.phone != Config.ADMIN_PHONE:
                admin.phone = Config.ADMIN_PHONE
                changed = True
            # 密钥（pepper）变更后旧哈希会校验失败：按配置密码重置，避免管理员被锁死
            if not verify_password(Config.ADMIN_PASSWORD, admin.password_hash):
                admin.password_hash = hash_password(Config.ADMIN_PASSWORD)
                changed = True
                print(f"[init] 管理员密码哈希已按当前配置重置: {Config.ADMIN_USERNAME}")
            if changed:
                session.add(admin)
                session.commit()


if __name__ == "__main__":
    init_and_seed()
    print("[init] 数据库初始化完成")
