from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Dish
router = APIRouter(prefix="/dishes", tags=["dishes"])

@router.get("")
def list_dishes(db: Session = Depends(get_db)):
    return [{"id": r.id, "code": r.code, "name": r.name, "portion_unit": r.portion_unit}
            for r in db.scalars(select(Dish).order_by(Dish.id)).all()]
