import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import BomLine, Ingredient, KitchenOrder, OrderLine, PrepRun
from app.services.bom_engine import explode_and_merge, result_to_dict
from app.services.stock_service import StockError, issue_prep_run
router = APIRouter(prefix="/prep", tags=["prep"])

@router.post("/run")
def run_prep(order_id: int = 1, db: Session = Depends(get_db)):
    order = db.get(KitchenOrder, order_id)
    if not order: raise HTTPException(404, "订单不存在")
    ols = [{"dish_id": l.dish_id, "portions": l.portions}
           for l in db.scalars(select(OrderLine).where(OrderLine.order_id == order_id)).all()]
    bom = [{"dish_id": b.dish_id, "ingredient_id": b.ingredient_id, "qty_per_portion": b.qty_per_portion}
           for b in db.scalars(select(BomLine)).all()]
    ings = {i.id: {"code": i.code, "name": i.name, "unit": i.unit, "stock_qty": i.stock_qty}
            for i in db.scalars(select(Ingredient)).all()}
    result = result_to_dict(explode_and_merge(ols, bom, ings))
    result["order"] = {"id": order.id, "code": order.code, "outlet": order.outlet}
    run = PrepRun(order_id=order_id, created_at=datetime.utcnow(), status="reserved",
                  result_json=json.dumps(result, ensure_ascii=False))
    db.add(run)
    for l in result["prep_lines"]:  # 生成即按需求占用，账面不动；与建单同一事务
        ing = db.get(Ingredient, l["ingredient_id"], with_for_update=True)
        ing.reserved_qty = round(ing.reserved_qty + l["need_qty"], 3)
    db.commit(); db.refresh(run)
    return {"id": run.id, "status": run.status, **result}

@router.post("/issue")
def issue(run_id: int, db: Session = Depends(get_db)):
    if db.get(PrepRun, run_id) is None:
        raise HTTPException(404, "备料单不存在")
    try:
        run = issue_prep_run(db, run_id)
    except StockError as e:
        db.rollback()  # 状态、占用、账面全部退回
        raise HTTPException(409, str(e))
    db.commit()
    return {"id": run.id, "status": run.status,
            "issued_at": run.issued_at.isoformat() if run.issued_at else None}

@router.get("/latest")
def latest(order_id: int = 1, db: Session = Depends(get_db)):
    run = db.scalars(select(PrepRun).where(PrepRun.order_id == order_id).order_by(PrepRun.id.desc())).first()
    if not run:
        return run_prep(order_id=order_id, db=db)
    data = json.loads(run.result_json)
    return {"id": run.id, "status": run.status, **data}

@router.get("/shortages")
def shortages(order_id: int = 1, db: Session = Depends(get_db)):
    data = latest(order_id=order_id, db=db)
    return {"order_id": order_id, "shortages": data.get("shortages", []), "stats": data.get("stats", {})}
