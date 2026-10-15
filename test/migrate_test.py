"""数据库 / 配置文件迁移测试（需求 16），独立运行，无需启动服务。

覆盖：
- migrate_env：.env 缺失键按 .env.example 补齐，已有值不被覆盖，修改前自动备份；
- migrate_db：旧库缺失列通过 ALTER TABLE 补齐，旧数据完整保留，变更前自动备份。

运行：
    .\\.venv\\Scripts\\python.exe test\\migrate_test.py
"""

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text  # noqa: E402

import backend.services.migrate as mig  # noqa: E402

passed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed
    print(f"[{'PASS' if condition else 'FAIL'}] {name}" + (f" -> {detail}" if detail else ""))
    if not condition:
        raise AssertionError(name)
    passed += 1


def test_migrate_env(tmp: Path) -> None:
    env = tmp / ".env"
    example = tmp / ".env.example"
    env.write_text("SECRET_KEY=my-old-secret\nFLASK_PORT=6000\n", encoding="utf-8")
    example.write_text(
        "# 注释行\nSECRET_KEY=template-secret\nFLASK_PORT=5000\nADMIN_PHONE=11111111111\n",
        encoding="utf-8",
    )

    old_base, old_backup = mig.BASE_DIR, mig.BACKUP_DIR
    mig.BASE_DIR, mig.BACKUP_DIR = tmp, tmp / "backups"
    try:
        added = mig.migrate_env()
        check("缺失键被补齐", added == ["ADMIN_PHONE"], str(added))
        content = env.read_text(encoding="utf-8")
        check("旧配置值保留不覆盖", "SECRET_KEY=my-old-secret" in content and "FLASK_PORT=6000" in content)
        check("新键追加到末尾", "ADMIN_PHONE=11111111111" in content)
        check("修改前自动备份", len(list((tmp / "backups").glob(".env.bak_*"))) == 1)

        again = mig.migrate_env()
        check("重复执行幂等（无新增）", again == [])

        # .env 不存在时按模板生成
        env.unlink()
        generated = mig.migrate_env()
        check(".env 缺失时按模板生成", env.exists() and "SECRET_KEY=template-secret" in env.read_text(encoding="utf-8"))
        check("生成返回全部键", len(generated) == 3)
    finally:
        mig.BASE_DIR, mig.BACKUP_DIR = old_base, old_backup


def test_migrate_db(tmp: Path) -> None:
    db_path = tmp / "old.db"
    eng = create_engine(f"sqlite:///{db_path.as_posix()}", connect_args={"check_same_thread": False})
    # 模拟旧版本库：user 表只有 id 和 password_hash 两列，且有存量数据
    with eng.begin() as conn:
        conn.execute(text('CREATE TABLE "user" (id INTEGER PRIMARY KEY, password_hash VARCHAR(255) NOT NULL)'))
        conn.execute(text("INSERT INTO \"user\" (id, password_hash) VALUES (1, 'legacy-hash')"))

    old_engine, old_db, old_backup = mig.engine, mig.Config.DB_PATH, mig.BACKUP_DIR
    mig.engine, mig.Config.DB_PATH, mig.BACKUP_DIR = eng, db_path, tmp / "backups"
    try:
        added = mig.migrate_db()
        check("旧表缺失列被识别", "user" in added and "username" in added["user"], str(added))
        with eng.connect() as conn:
            row = conn.execute(text('SELECT password_hash, is_admin, is_active FROM "user" WHERE id = 1')).fetchone()
            cols = {r[1] for r in conn.execute(text('PRAGMA table_info("user")'))}
        check("旧数据完整保留", row[0] == "legacy-hash")
        check("新列带默认值可查询", row[1] == 0 and row[2] == 1, f"is_admin={row[1]} is_active={row[2]}")
        check("模型全部字段已落库", {"username", "phone", "email", "created_at", "updated_at"} <= cols)
        check("变更前自动备份数据库", len(list((tmp / "backups").glob("old.db.bak_*"))) == 1)

        again = mig.migrate_db()
        check("重复执行幂等（无变更）", again == {})
    finally:
        mig.engine, mig.Config.DB_PATH, mig.BACKUP_DIR = old_engine, old_db, old_backup
        eng.dispose()


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="sourcelink_migrate_test_"))
    try:
        test_migrate_env(tmp)
        test_migrate_db(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n全部通过，共 {passed} 项检查。")


if __name__ == "__main__":
    main()
