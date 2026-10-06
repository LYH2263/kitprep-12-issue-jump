from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Ingredient
from app.services.stock import StockError, issue_direct

router = APIRouter(prefix="/inventory", tags=["inventory"])
QTY_DP = 3


def _row(r: Ingredient) -> dict:
    # 账面 stock_qty、占用 reserved_qty、可用 = 账面 - 占用，三者同源，备料台与库存页共用
    return {
        "id": r.id,
        "code": r.code,
        "name": r.name,
        "unit": r.unit,
        "stock_qty": round(r.stock_qty, QTY_DP),
        "reserved_qty": round(r.reserved_qty, QTY_DP),
        "available_qty": round(r.stock_qty - r.reserved_qty, QTY_DP),
    }


class IssueBody(BaseModel):
    qty: float


@router.get("")
def list_inventory(db: Session = Depends(get_db)):
    return [_row(r) for r in db.scalars(select(Ingredient).order_by(Ingredient.id)).all()]


@router.post("/{ingredient_id}/issue")
def issue_stock(ingredient_id: int, body: IssueBody, db: Session = Depends(get_db)):
    try:
        # 库存页出库与备料台领料同口径：都经 stock.deduct_book 只扣一次账面
        ing = issue_direct(db, ingredient_id, body.qty)
        db.commit()
    except StockError as exc:
        db.rollback()
        raise HTTPException(exc.status_code, str(exc))
    return _row(ing)
