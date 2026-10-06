from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


# 轻量列自愈：旧库已存在的表不会被 create_all 改结构，这里补齐新增列。
# （旧 prep_runs 行没有预占明细，保持存档不可领；新列仅让状态字段可正常读写。）
_ADDED_COLUMNS = {
    "ingredients": [("reserved_qty", "FLOAT DEFAULT 0.0")],
    "prep_runs": [("status", "VARCHAR(16)")],
}


def ensure_columns() -> None:
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in _ADDED_COLUMNS.items():
            if not inspector.has_table(table):
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        # 历史备料单没有预占明细，统一标记为已领存档，杜绝被这次领料流程改字或重复扣账
        conn.execute(text("UPDATE prep_runs SET status = 'issued' WHERE status IS NULL"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
