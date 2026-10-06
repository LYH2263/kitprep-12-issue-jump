import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SEED_ON_EMPTY", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import (
    BomLine,
    Dish,
    Ingredient,
    KitchenOrder,
    OrderLine,
)


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()

    # 菜品 A：每份用肉 0.2；菜品 B：每份用米 0.1
    d1 = Dish(code="D-A", name="菜A")
    d2 = Dish(code="D-B", name="菜B")
    db.add_all([d1, d2])
    db.flush()
    meat = Ingredient(code="I-MEAT", name="肉", unit="kg", stock_qty=8.0, reserved_qty=0.0)
    rice = Ingredient(code="I-RICE", name="米", unit="kg", stock_qty=20.0, reserved_qty=0.0)
    oil = Ingredient(code="I-OIL", name="油", unit="L", stock_qty=1.0, reserved_qty=0.0)
    db.add_all([meat, rice, oil])
    db.flush()
    db.add_all([
        BomLine(dish_id=d1.id, ingredient_id=meat.id, qty_per_portion=0.2),
        BomLine(dish_id=d2.id, ingredient_id=rice.id, qty_per_portion=0.1),
        BomLine(dish_id=d1.id, ingredient_id=oil.id, qty_per_portion=0.01),
    ])
    order = KitchenOrder(code="KO-1", outlet="测试门店", status="open")
    db.add(order)
    db.flush()
    db.add_all([
        OrderLine(order_id=order.id, dish_id=d1.id, portions=10),  # 肉 2.0、油 0.1
        OrderLine(order_id=order.id, dish_id=d2.id, portions=5),   # 米 0.5
    ])
    db.commit()

    def override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield Session, {"meat": meat.id, "rice": rice.id, "oil": oil.id, "order": order.id}
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db_session):
    return TestClient(app)
