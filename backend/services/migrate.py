"""数据库 / 配置文件迁移（需求 16）。

对数据库或配置文件进行修改、覆盖类操作时，保留并迁移旧内容：

- migrate_env()：以 .env.example 为模板，把 .env 中缺失的配置键追加补齐，
  已有配置项的值原样保留（绝不覆盖），修改前自动备份原 .env。
- migrate_db()：对比 SQLModel 元数据与现有 SQLite 表结构，
  已存在的表缺失的列通过 ALTER TABLE ADD COLUMN 补齐（旧数据全部保留），
  执行结构变更前自动把数据库文件备份到 db/backups/ 目录。

两个迁移都在服务启动时（init_and_seed）自动执行，无需人工干预。
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import text
from sqlmodel import SQLModel

from ..config import BASE_DIR, Config
from ..database import engine

BACKUP_DIR = Config.DB_PATH.parent / "backups"


def _backup_file(path: Path) -> Path:
    """把文件复制到 db/backups/ 并附加时间戳，返回备份路径。"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = BACKUP_DIR / f"{path.name}.bak_{stamp}"
    shutil.copy2(path, target)
    return target


# ---------------- .env 配置迁移 ----------------


def _parse_env_keys(path: Path) -> list[str]:
    keys: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            keys.append(stripped.split("=", 1)[0].strip())
    return keys


def migrate_env() -> list[str]:
    """把 .env.example 中有而 .env 缺失的键追加到 .env，返回补齐的键列表。

    只追加缺失项，不修改已有键的值；.env 不存在时直接以模板生成。
    """
    env_path = BASE_DIR / ".env"
    example_path = BASE_DIR / ".env.example"
    if not example_path.exists():
        return []

    if not env_path.exists():
        shutil.copy2(example_path, env_path)
        print("[migrate] .env 不存在，已按 .env.example 模板生成")
        return _parse_env_keys(env_path)

    existed = set(_parse_env_keys(env_path))
    missing_lines = [
        line
        for line in example_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        and not line.strip().startswith("#")
        and "=" in line
        and line.split("=", 1)[0].strip() not in existed
    ]
    if not missing_lines:
        return []

    backup = _backup_file(env_path)
    with env_path.open("a", encoding="utf-8") as f:
        f.write("\n# ---- 版本升级自动补齐的配置项（上方旧配置值原样保留） ----\n")
        for line in missing_lines:
            f.write(line + "\n")
    added = [line.split("=", 1)[0].strip() for line in missing_lines]
    print(f"[migrate] .env 已补齐缺失配置项 {added}，原文件备份: {backup}；新配置下次启动生效")
    return added


# ---------------- SQLite 数据库结构迁移 ----------------

# 列类型 -> SQLite 默认值字面量：为 NOT NULL 且无默认值的列兜底
_FALLBACK_DEFAULTS = (
    ("VARCHAR", "''"),
    ("CHAR", "''"),
    ("TEXT", "''"),
    ("BOOLEAN", "0"),
    ("INTEGER", "0"),
    ("FLOAT", "0.0"),
    ("NUMERIC", "0"),
    ("DATETIME", "'1970-01-01 00:00:00'"),
    ("DATE", "'1970-01-01'"),
)


def _column_ddl(column) -> str:
    """生成 ALTER TABLE ADD COLUMN 用的列定义（含默认值，保证旧表有数据时也能加列）。"""
    col_type = column.type.compile(dialect=engine.dialect)
    ddl = f'"{column.name}" {col_type}'
    default = column.default.arg if column.default is not None and column.default.is_scalar else None
    if default is not None:
        if isinstance(default, bool):
            literal = str(int(default))
        elif isinstance(default, str):
            literal = f"'{default}'"
        else:
            literal = str(default)
        return f"{ddl} NOT NULL DEFAULT {literal}"
    if not column.nullable:
        for prefix, literal in _FALLBACK_DEFAULTS:
            if col_type.upper().startswith(prefix):
                return f"{ddl} NOT NULL DEFAULT {literal}"
    return ddl


def migrate_db() -> dict[str, list[str]]:
    """给已存在的表补齐缺失的列（旧数据保留），返回 {表名: [新增列]}；无变更返回空。"""
    from .. import models  # noqa: F401  导入即注册元数据

    added: dict[str, list[str]] = {}
    with engine.connect() as conn:
        for table in SQLModel.metadata.sorted_tables:
            existing = {row[1] for row in conn.execute(text(f'PRAGMA table_info("{table.name}")'))}
            if not existing:
                continue  # 缺失的表由 create_all 负责创建
            missing = [c.name for c in table.columns if c.name not in existing]
            if missing:
                added[table.name] = missing

    if not added:
        return {}

    backup = _backup_file(Config.DB_PATH)
    with engine.begin() as conn:
        for table_name, columns in added.items():
            table = SQLModel.metadata.tables[table_name]
            for col_name in columns:
                conn.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN {_column_ddl(table.columns[col_name])}'))
    print(f"[migrate] 数据库结构已迁移（旧数据保留），原库备份: {backup}；变更: {added}")
    return added
