from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Ingredient
from app.services.stock_service import StockError, stock_out_once
router = APIRouter(prefix="/inventory", tags=["inventory"])

def _row(r: Ingredient) -> dict:
    return {"id": r.id, "code": r.code, "name": r.name, "unit": r.unit,
            "stock_qty": r.stock_qty, "reserved_qty": r.reserved_qty,
            "available_qty": round(r.stock_qty - r.reserved_qty, 3)}

@router.get("")
def list_inventory(db: Session = Depends(get_db)):
    return [_row(r) for r in db.scalars(select(Ingredient).order_by(Ingredient.id)).all()]

@router.post("/stock-out")
def stock_out(ingredient_id: int, qty: float, db: Session = Depends(get_db)):
    # 与备料台领料同一口径：账面只扣一笔，失败整笔退回
    try:
        ing = stock_out_once(db, ingredient_id, qty)
    except StockError as e:
        db.rollback()
        raise HTTPException(409, str(e))
    db.commit()
    return _row(ing)
