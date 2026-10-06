"""领料出库口径测试：预占转出库、只扣一次、重复领失败、失败全回滚、旧单不改、库存页同口径。"""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="kitprep-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["SEED_ON_EMPTY"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.models import BomLine, Dish, Ingredient, KitchenOrder, OrderLine, PrepRun


@pytest.fixture()
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def client(db):
    return TestClient(app)


def make_order(db, stock_a=10.0, stock_b=5.0, portions=4):
    """一份订单：菜 D-T1 × portions；每份需 A 0.5、B 0.2 → 需 A 2.0、B 0.8。"""
    d1 = Dish(code="D-T1", name="测试菜", portion_unit="份")
    a = Ingredient(code="I-A", name="原料A", unit="kg", stock_qty=stock_a)
    b = Ingredient(code="I-B", name="原料B", unit="kg", stock_qty=stock_b)
    db.add_all([d1, a, b]); db.flush()
    db.add_all([
        BomLine(dish_id=d1.id, ingredient_id=a.id, qty_per_portion=0.5),
        BomLine(dish_id=d1.id, ingredient_id=b.id, qty_per_portion=0.2),
    ])
    o = KitchenOrder(code="KO-T1", outlet="测试门店", status="open")
    db.add(o); db.flush()
    db.add(OrderLine(order_id=o.id, dish_id=d1.id, portions=portions))
    db.commit()
    return o, a, b


def test_run_reserves_without_touching_stock(client, db):
    o, a, b = make_order(db)
    res = client.post(f"/api/prep/run?order_id={o.id}")
    assert res.status_code == 200
    assert res.json()["status"] == "reserved"
    db.refresh(a); db.refresh(b)
    assert (a.stock_qty, b.stock_qty) == (10.0, 5.0)      # 账面不动
    assert (a.reserved_qty, b.reserved_qty) == (2.0, 0.8)  # 只占用


def test_issue_converts_reservation_exactly_once(client, db):
    o, a, b = make_order(db)
    run_id = client.post(f"/api/prep/run?order_id={o.id}").json()["id"]
    res = client.post(f"/api/prep/issue?run_id={run_id}")
    assert res.status_code == 200
    assert res.json()["status"] == "issued"
    db.refresh(a); db.refresh(b)
    assert (a.reserved_qty, b.reserved_qty) == (0.0, 0.0)  # 占用清掉
    assert (a.stock_qty, b.stock_qty) == (8.0, 4.2)        # 账面只按占用扣一次
    inv = {r["code"]: r for r in client.get("/api/inventory").json()}
    assert inv["I-A"]["stock_qty"] == 8.0 and inv["I-A"]["reserved_qty"] == 0.0
    assert inv["I-B"]["stock_qty"] == 4.2 and inv["I-B"]["reserved_qty"] == 0.0


def test_issue_twice_fails_without_side_effects(client, db):
    o, a, b = make_order(db)
    run_id = client.post(f"/api/prep/run?order_id={o.id}").json()["id"]
    assert client.post(f"/api/prep/issue?run_id={run_id}").status_code == 200
    res = client.post(f"/api/prep/issue?run_id={run_id}")
    assert res.status_code == 409
    db.refresh(a); db.refresh(b)
    assert (a.stock_qty, b.stock_qty) == (8.0, 4.2)        # 账面不再动
    assert (a.reserved_qty, b.reserved_qty) == (0.0, 0.0)  # 占用不再动


def test_issue_failure_rolls_back_everything(client, db):
    o, a, b = make_order(db)
    run_id = client.post(f"/api/prep/run?order_id={o.id}").json()["id"]
    # 从库存页出库 9，使 A 账面 1.0 低于本单占用 2.0，领料必然失败
    assert client.post(f"/api/inventory/stock-out?ingredient_id={a.id}&qty=9").status_code == 200
    res = client.post(f"/api/prep/issue?run_id={run_id}")
    assert res.status_code == 409
    run = db.get(PrepRun, run_id)
    db.refresh(a); db.refresh(b)
    assert run.status == "reserved" and run.issued_at is None  # 状态退回
    assert a.stock_qty == 1.0 and a.reserved_qty == 2.0        # 账面、占用都退回
    assert b.stock_qty == 5.0 and b.reserved_qty == 0.8        # 其他原料也不许扣一半


def test_older_runs_not_rewritten(client, db):
    o, a, b = make_order(db)
    run1 = client.post(f"/api/prep/run?order_id={o.id}").json()["id"]
    run2 = client.post(f"/api/prep/run?order_id={o.id}").json()["id"]
    json1_before = db.get(PrepRun, run1).result_json
    assert client.post(f"/api/prep/issue?run_id={run2}").status_code == 200
    db.expire_all()
    run1_row = db.get(PrepRun, run1)
    assert run1_row.status == "reserved"          # 旧单状态不被改
    assert run1_row.result_json == json1_before   # 旧单内容不被改字
    db.refresh(a)
    assert a.reserved_qty == 2.0  # 只剩 run1 的占用（2.0 + 2.0 − 2.0）
    assert a.stock_qty == 8.0     # 账面只按 run2 那一笔扣


def test_inventory_stock_out_same_rule(client, db):
    o, a, b = make_order(db)
    res = client.post(f"/api/inventory/stock-out?ingredient_id={a.id}&qty=1.5")
    assert res.status_code == 200
    assert res.json()["stock_qty"] == 8.5
    db.refresh(a)
    assert a.stock_qty == 8.5  # 只扣一笔
    res = client.post(f"/api/inventory/stock-out?ingredient_id={a.id}&qty=99")
    assert res.status_code == 409  # 余额不足：失败且账面不动
    db.refresh(a)
    assert a.stock_qty == 8.5
    assert client.post(f"/api/inventory/stock-out?ingredient_id={a.id}&qty=0").status_code == 409


def test_issue_missing_run_404(client, db):
    assert client.post("/api/prep/issue?run_id=999").status_code == 404
