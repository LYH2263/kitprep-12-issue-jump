"""统一库存口径：预占、领料转出库、手工出库都走这里。

口径约定：
- stock_qty 是账面结存（实物在库，含已预占部分）；reserved_qty 是备料单已占未领的量。
- 出库只有 deduct_book() 一个扣减入口，备料台领料和库存页出库共用，谁都不许多扣一次。
- 领料 = 把本单每一笔预占转成真正出库：账面按该笔预占扣一次，同时把这笔占用清掉。
- 所有函数都在调用方的事务内执行，任一步失败由调用方回滚，状态/占用/账面整体退回。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import (
    Ingredient,
    PrepReservation,
    PrepRun,
    PREP_STATUS_ISSUED,
)

EPS = 1e-9
QTY_DP = 6


class StockError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _q(value: float) -> float:
    return round(float(value), QTY_DP)


def _lock_ingredients(db: Session, ingredient_ids: list[int]) -> dict[int, Ingredient]:
    ids = sorted(set(ingredient_ids))
    if not ids:
        return {}
    rows = db.scalars(
        select(Ingredient).where(Ingredient.id.in_(ids)).order_by(Ingredient.id).with_for_update()
    ).all()
    return {i.id: i for i in rows}


def deduct_book(ing: Ingredient, qty: float) -> None:
    """唯一的账面出库扣减：结存够才扣，且只扣传入的这一笔。"""
    if qty is None or qty <= 0:
        raise StockError("出库数量必须大于 0")
    qty = float(qty)
    if ing.stock_qty + EPS < qty:
        raise StockError(
            f"{ing.name} 账面结存不足：账面 {_q(ing.stock_qty)} {ing.unit}，需出库 {_q(qty)} {ing.unit}"
        )
    ing.stock_qty = _q(ing.stock_qty - qty)


def reserve_needs(db: Session, run_id: int, needs: list[dict]) -> list[PrepReservation]:
    """生成备料单时预占：按可用量（账面-已占）占用，缺料部分只占可用余额。"""
    ings = _lock_ingredients(db, [n["ingredient_id"] for n in needs])
    rows: list[PrepReservation] = []
    for n in sorted(needs, key=lambda x: x["ingredient_id"]):
        ing = ings.get(int(n["ingredient_id"]))
        if ing is None:
            raise StockError("原料不存在", 404)
        need_qty = float(n["need_qty"])
        available = max(0.0, _q(ing.stock_qty - ing.reserved_qty))
        take = _q(min(need_qty, available))
        if take > 0:
            ing.reserved_qty = _q(ing.reserved_qty + take)
        rows.append(
            PrepReservation(
                run_id=run_id,
                ingredient_id=ing.id,
                need_qty=_q(need_qty),
                reserved_qty=take,
            )
        )
    db.add_all(rows)
    db.flush()
    return rows


def lock_run(db: Session, run_id: int) -> PrepRun | None:
    return db.scalar(select(PrepRun).where(PrepRun.id == run_id).with_for_update())


def issue_run(db: Session, run_id: int) -> PrepRun:
    """把一张备料单的预占转成真正出库。

    已领的单直接拒绝（并发/重复点击都靠行锁 + 状态判定挡住），占用和账面一律不动。
    中途任一笔扣减失败抛 StockError，调用方回滚后状态、占用、账面全部维持原样。
    """
    run = lock_run(db, run_id)
    if run is None:
        raise StockError("备料单不存在", 404)
    if run.status == PREP_STATUS_ISSUED:
        raise StockError("该备料单已领料，不能重复领料", 409)

    reservations = db.scalars(
        select(PrepReservation)
        .where(PrepReservation.run_id == run_id)
        .order_by(PrepReservation.ingredient_id)
    ).all()
    total_reserved = _q(sum(r.reserved_qty for r in reservations))
    if total_reserved <= 0:
        raise StockError("该备料单没有可领的预占量，不能领料")

    ings = _lock_ingredients(db, [r.ingredient_id for r in reservations])
    for r in reservations:
        if r.reserved_qty <= 0:
            continue
        ing = ings.get(r.ingredient_id)
        if ing is None or ing.reserved_qty + EPS < r.reserved_qty:
            raise StockError("预占数据异常，领料已中止")
        # 与库存页出库同口径扣账面；成功后才清掉本单这笔占用。
        deduct_book(ing, r.reserved_qty)
        ing.reserved_qty = _q(ing.reserved_qty - r.reserved_qty)
        r.issued_qty = r.reserved_qty

    run.status = PREP_STATUS_ISSUED
    db.flush()
    return run


def issue_direct(db: Session, ingredient_id: int, qty: float) -> Ingredient:
    """库存页手工出库：与备料台领料走同一个账面扣减函数。"""
    ing = db.scalar(
        select(Ingredient).where(Ingredient.id == ingredient_id).with_for_update()
    )
    if ing is None:
        raise StockError("原料不存在", 404)
    deduct_book(ing, qty)
    db.flush()
    return ing
