"""领料出库全口径测试。

核心不变量：
1. 生成备料单：只占可用量，账面不动；缺料只占余额。
2. 领料成功：本单预占转真正出库——占用清掉、账面只按占用那笔扣一次。
3. 已领再领：409 失败，占用和账面都不许再动。
4. 领料失败：状态、占用、账面整体退回。
5. 更早存档的单不被新领料改字，其占用与账面保留。
6. 备料台领料与库存页出库同一口径。
"""
from sqlalchemy import select

from app.models.models import (
    Ingredient,
    PrepReservation,
    PrepRun,
    PREP_STATUS_ISSUED,
    PREP_STATUS_RESERVED,
)
from app.services.stock import issue_run, reserve_needs


def _ing(session, ids, key):
    return session.get(Ingredient, ids[key])


def _reservations(session, run_id):
    return session.scalars(
        select(PrepReservation).where(PrepReservation.run_id == run_id)
    ).all()


def test_run_reserves_book_unchanged_and_shortage_partial(client, db_session):
    """生成即预占：占用增加、账面不动；可用不足时只占余额，缺料保留为缺口。"""
    Session, ids = db_session
    res = client.post("/api/prep/run", params={"order_id": ids["order"]})
    assert res.status_code == 200
    run_id = res.json()["run_id"]

    s = Session()
    meat = _ing(s, ids, "meat")
    oil = _ing(s, ids, "oil")
    assert meat.stock_qty == 8.0          # 账面不动
    assert meat.reserved_qty == 2.0       # 10 份 * 0.2
    assert oil.stock_qty == 1.0 and oil.reserved_qty == 0.1

    # 油：库存 1.0，需求 0.1，不缺；把油账面调到不足后验证部分预占
    oil.stock_qty = 0.04
    oil.reserved_qty = 0.0
    s.commit()

    res2 = client.post("/api/prep/run", params={"order_id": ids["order"]})
    body = res2.json()
    oil_line = [l for l in body["prep_lines"] if l["ingredient_id"] == ids["oil"]][0]
    assert oil_line["reserved_qty"] == 0.04      # 只占可用余额
    assert oil_line["shortage"] > 0
    s.close()


def test_issue_converts_reservation_single_book_deduction(client, db_session):
    """成功领料：占用清掉、账面只按占用那笔扣一次，状态已领。"""
    Session, ids = db_session
    body = client.post("/api/prep/run", params={"order_id": ids["order"]}).json()
    run_id = body["run_id"]

    res = client.post(f"/api/prep/runs/{run_id}/issue")
    assert res.status_code == 200
    out = res.json()
    assert out["status"] == PREP_STATUS_ISSUED
    for line in out["prep_lines"]:
        assert line["reserved_qty"] == 0.0

    s = Session()
    meat = _ing(s, ids, "meat")
    rice = _ing(s, ids, "rice")
    assert meat.stock_qty == 6.0       # 8 - 2.0，只扣一次
    assert meat.reserved_qty == 0.0
    assert rice.stock_qty == 19.5      # 20 - 0.5
    assert rice.reserved_qty == 0.0
    assert s.get(PrepRun, run_id).status == PREP_STATUS_ISSUED
    s.close()


def test_double_issue_rejected_and_accounts_untouched(client, db_session):
    """已领的单再领必须失败（409），占用和账面都不许再动。"""
    Session, ids = db_session
    run_id = client.post("/api/prep/run", params={"order_id": ids["order"]}).json()["run_id"]
    assert client.post(f"/api/prep/runs/{run_id}/issue").status_code == 200

    s = Session()
    meat_before = _ing(s, ids, "meat")
    book, reserved = meat_before.stock_qty, meat_before.reserved_qty
    s.close()

    again = client.post(f"/api/prep/runs/{run_id}/issue")
    assert again.status_code == 409

    s = Session()
    meat_after = _ing(s, ids, "meat")
    assert meat_after.stock_qty == book
    assert meat_after.reserved_qty == reserved
    assert s.get(PrepRun, run_id).status == PREP_STATUS_ISSUED
    s.close()


def test_failed_issue_rolls_back_all(client, db_session, monkeypatch):
    """领料中途失败：状态、占用、账面全部退回（不允许扣了一半）。"""
    Session, ids = db_session
    run_id = client.post("/api/prep/run", params={"order_id": ids["order"]}).json()["run_id"]

    # 让扣减到第二行（米，按 ingredient_id 顺序在肉之后）时账面不足
    s = Session()
    s.get(Ingredient, ids["rice"]).stock_qty = 0.1  # 占用 0.5，实物只够 0.1
    s.commit()
    s.close()

    res = client.post(f"/api/prep/runs/{run_id}/issue")
    assert res.status_code == 400

    s = Session()
    run = s.get(PrepRun, run_id)
    assert run.status == PREP_STATUS_RESERVED        # 状态退回
    meat = _ing(s, ids, "meat")
    rice = _ing(s, ids, "rice")
    assert meat.stock_qty == 8.0 and meat.reserved_qty == 2.0   # 第一笔也退回
    assert rice.reserved_qty == 0.5
    for r in _reservations(s, run_id):
        assert r.issued_qty == 0.0
    s.close()


def test_archived_run_untouched_by_later_issue(db_session):
    """更早存档的单不被后来的领料改字，其占用与账面保留。"""
    Session, ids = db_session
    s = Session()

    # 第一张单：预占并保留（不领）
    from app.api.prep import _load_inputs
    import json
    from app.models.models import PrepRun
    from app.services.bom_engine import explode_and_merge, result_to_dict

    order, ols, bom, ings = _load_inputs(s, ids["order"])
    result = result_to_dict(explode_and_merge(ols, bom, ings))
    old = PrepRun(order_id=ids["order"], result_json=json.dumps(result, ensure_ascii=False),
                  status=PREP_STATUS_RESERVED)
    s.add(old)
    s.flush()
    old_rows = reserve_needs(s, old.id, result["prep_lines"])
    s.commit()
    old_json = old.result_json
    old_reserved = {r.ingredient_id: r.reserved_qty for r in old_rows}
    old_id = old.id
    s.close()

    # 第二张单：预占后领料
    s = Session()
    result2 = result_to_dict(explode_and_merge(*_load_inputs(s, ids["order"])[1:]))
    new = PrepRun(order_id=ids["order"], result_json=json.dumps(result2, ensure_ascii=False),
                  status=PREP_STATUS_RESERVED)
    s.add(new)
    s.flush()
    reserve_needs(s, new.id, result2["prep_lines"])
    s.commit()
    issue_run(s, new.id)
    s.commit()

    # 老单存档原样、占用还挂着
    s = Session()
    reloaded_old = s.get(PrepRun, old_id)
    assert reloaded_old.result_json == old_json
    assert reloaded_old.status == PREP_STATUS_RESERVED
    for r in _reservations(s, old_id):
        assert r.reserved_qty == old_reserved[r.ingredient_id]
        assert r.issued_qty == 0.0
    meat = _ing(s, ids, "meat")
    # 肉：账面 8，老单占 2 + 新单占 2；新单领走 2 后账面 6，老单的 2 占用仍挂
    assert meat.stock_qty == 6.0
    assert meat.reserved_qty == 2.0
    s.close()


def test_inventory_issue_same_rule_as_prep(client, db_session):
    """库存页出库与备料台领料同一口径：都只扣一次账面，不足同样失败回滚。"""
    Session, ids = db_session
    ok = client.post(f"/api/inventory/{ids['meat']}/issue", json={"qty": 1.5})
    assert ok.status_code == 200
    assert ok.json()["stock_qty"] == 6.5
    assert ok.json()["reserved_qty"] == 0.0
    assert ok.json()["available_qty"] == 6.5

    bad = client.post(f"/api/inventory/{ids['meat']}/issue", json={"qty": 99})
    assert bad.status_code == 400
    s = Session()
    assert _ing(s, ids, "meat").stock_qty == 6.5   # 失败没动账
    s.close()

    # 备料台占用的量，库存页出库再扣账面时也按账面结存判断（同一函数）
    client.post("/api/prep/run", params={"order_id": ids["order"]})
    s = Session()
    meat = _ing(s, ids, "meat")
    assert meat.stock_qty == 6.5 and meat.reserved_qty == 2.0
    s.close()
