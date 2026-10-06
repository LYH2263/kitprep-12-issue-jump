from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Ingredient
router = APIRouter(prefix="/inventory", tags=["inventory"])

@router.get("")
def list_inventory(db: Session = Depends(get_db)):
    return [{"id": r.id, "code": r.code, "name": r.name, "unit": r.unit, "stock_qty": r.stock_qty}
            for r in db.scalars(select(Ingredient).order_by(Ingredient.id)).all()]
