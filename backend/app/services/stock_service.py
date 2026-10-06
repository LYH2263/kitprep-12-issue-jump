"""出库同一口径：备料台领料与库存页出库共用同一套扣账逻辑。

口径约定：
- 账面结存（stock_qty）只在真正出库时扣一次；
- 生成备料单时只增加占用（reserved_qty），不动账面；
- 领料把这张单上的预占转成出库：占用按该单那一笔清掉，账面按同一笔扣一次；
- 本模块只改对象不提交事务，由调用方统一 commit / rollback，
  任何一步失败，状态、占用、账面全部退回。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.models import Ingredient, PrepRun

EPS = 1e-9


class StockError(Exception):
    """库存操作失败（余额不足 / 重复领料 / 单不存在）。调用方应回滚事务。"""


def _ensure_balance(ing: Ingredient | None, qty: float) -> Ingredient:
    if ing is None:
        raise StockError("原料不存在")
    if ing.stock_qty + EPS < qty:
        raise StockError(f"账面结存不足：{ing.name} 现存 {ing.stock_qty}，需出 {qty}")
    return ing


def stock_out_once(db: Session, ingredient_id: int, qty: float) -> Ingredient:
    """账面结存只扣这一笔；余额不足抛 StockError，不改动任何数据。"""
    if qty <= 0:
        raise StockError("出库数量必须大于 0")
    ing = _ensure_balance(db.get(Ingredient, ingredient_id, with_for_update=True), qty)
    ing.stock_qty = round(ing.stock_qty - qty, 3)
    return ing


def issue_prep_run(db: Session, run_id: int) -> PrepRun:
    """把这张备料单的预占转成真正出库。

    先整体校验再统一落账，避免扣到一半；已领过的单直接失败，
    占用和账面都不再动；只动这一张单，更早存档的单不受影响。
    """
    run = db.get(PrepRun, run_id, with_for_update=True)
    if run is None:
        raise StockError("备料单不存在")
    if run.status == "issued":
        raise StockError("该备料单已领料，不能重复出库")
    lines = json.loads(run.result_json).get("prep_lines", [])
    ings = {l["ingredient_id"]: db.get(Ingredient, l["ingredient_id"], with_for_update=True)
            for l in lines}
    for l in lines:  # 先全部校验通过
        _ensure_balance(ings[l["ingredient_id"]], l["need_qty"])
    for l in lines:  # 再统一落账：占用清掉、账面只按这一笔扣一次
        ing = ings[l["ingredient_id"]]
        ing.reserved_qty = round(ing.reserved_qty - l["need_qty"], 3)
        ing.stock_qty = round(ing.stock_qty - l["need_qty"], 3)
    run.status = "issued"
    run.issued_at = datetime.utcnow()
    return run
