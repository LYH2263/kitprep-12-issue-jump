import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import (
    BomLine,
    Ingredient,
    KitchenOrder,
    OrderLine,
    PrepReservation,
    PrepRun,
    PREP_STATUS_RESERVED,
)
from app.services.bom_engine import explode_and_merge, result_to_dict
from app.services.stock import StockError, issue_run, reserve_needs

router = APIRouter(prefix="/prep", tags=["prep"])


def _load_inputs(db: Session, order_id: int):
    order = db.get(KitchenOrder, order_id)
    if not order:
        raise HTTPException(404, "订单不存在")
    ols = [{"dish_id": l.dish_id, "portions": l.portions}
           for l in db.scalars(select(OrderLine).where(OrderLine.order_id == order_id)).all()]
    bom = [{"dish_id": b.dish_id, "ingredient_id": b.ingredient_id, "qty_per_portion": b.qty_per_portion}
           for b in db.scalars(select(BomLine)).all()]
    ings = {i.id: {"code": i.code, "name": i.name, "unit": i.unit, "stock_qty": i.stock_qty}
            for i in db.scalars(select(Ingredient)).all()}
    return order, ols, bom, ings


def _serialize(db: Session, run: PrepRun) -> dict:
    # result_json 是生成时存档，任何后续领料都不改字；只在其上叠加实时占用/账面。
    data = json.loads(run.result_json or "{}")
    reservations = db.scalars(
        select(PrepReservation).where(PrepReservation.run_id == run.id)
    ).all()
    res_by_ing = {r.ingredient_id: r for r in reservations}
    live = {i.id: i for i in db.scalars(select(Ingredient)).all()}

    lines = []
    for line in data.get("prep_lines", []):
        r = res_by_ing.get(line["ingredient_id"])
        ing = live.get(line["ingredient_id"])
        # 明细行 reserved_qty 是生成时的占用存档（不可变），未领余额 = 占用 - 已领
        outstanding = round((r.reserved_qty - r.issued_qty) if r else 0.0, 3)
        lines.append({
            **line,
            "reserved_qty": outstanding,
            "issued_qty": round(r.issued_qty if r else 0.0, 3),
            "book_qty": round(ing.stock_qty if ing else 0.0, 3),
            "available_qty": round(
                (ing.stock_qty - ing.reserved_qty) if ing else 0.0, 3
            ),
        })
    shortages = [l for l in lines if l["shortage"] > 0]
    data["prep_lines"] = lines
    data["shortages"] = shortages
    data["run_id"] = run.id
    data["status"] = run.status
    return data


@router.post("/run")
def run_prep(order_id: int = 1, db: Session = Depends(get_db)):
    order, ols, bom, ings = _load_inputs(db, order_id)
    result = result_to_dict(explode_and_merge(ols, bom, ings))
    result["order"] = {"id": order.id, "code": order.code, "outlet": order.outlet}

    run = PrepRun(
        order_id=order_id,
        created_at=datetime.utcnow(),
        result_json=json.dumps(result, ensure_ascii=False),
        status=PREP_STATUS_RESERVED,
    )
    db.add(run)
    db.flush()  # 取 run.id，预占明细要挂在它下面
    try:
        # 生成即预占：账面不动，只占可用量；任一行失败整体回滚，单据不留半占状态。
        reserve_needs(db, run.id, result["prep_lines"])
        db.commit()
    except StockError as exc:
        db.rollback()
        raise HTTPException(exc.status_code, str(exc))
    db.refresh(run)
    return _serialize(db, run)


@router.post("/runs/{run_id}/issue")
def issue_prep_run(run_id: int, db: Session = Depends(get_db)):
    try:
        run = issue_run(db, run_id)  # 预占转出库：占用清掉、账面只按占用那笔扣一次
        db.commit()
    except StockError as exc:
        # 已领再领 / 扣减失败：状态、占用、账面全部退回
        db.rollback()
        raise HTTPException(exc.status_code, str(exc))
    return _serialize(db, run)


@router.get("/latest")
def latest(order_id: int = 1, db: Session = Depends(get_db)):
    run = db.scalars(
        select(PrepRun).where(PrepRun.order_id == order_id).order_by(PrepRun.id.desc())
    ).first()
    if not run:
        return run_prep(order_id=order_id, db=db)
    return _serialize(db, run)


@router.get("/shortages")
def shortages(order_id: int = 1, db: Session = Depends(get_db)):
    data = latest(order_id=order_id, db=db)
    return {"order_id": order_id, "shortages": data.get("shortages", []), "stats": data.get("stats", {})}
