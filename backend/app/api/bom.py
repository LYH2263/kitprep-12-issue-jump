from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import BomLine, Dish, Ingredient
router = APIRouter(prefix="/bom", tags=["bom"])

@router.get("")
def list_bom(db: Session = Depends(get_db)):
    dishes = {d.id: d for d in db.scalars(select(Dish)).all()}
    ings = {i.id: i for i in db.scalars(select(Ingredient)).all()}
    rows = db.scalars(select(BomLine).order_by(BomLine.dish_id, BomLine.id)).all()
    return [{"id": r.id, "dish_id": r.dish_id, "dish_name": dishes[r.dish_id].name,
             "ingredient_id": r.ingredient_id, "ingredient_name": ings[r.ingredient_id].name,
             "qty_per_portion": r.qty_per_portion, "unit": ings[r.ingredient_id].unit} for r in rows]

@router.get("/tree")
def bom_tree(db: Session = Depends(get_db)):
    dishes = db.scalars(select(Dish).order_by(Dish.id)).all()
    ings = {i.id: i for i in db.scalars(select(Ingredient)).all()}
    lines = db.scalars(select(BomLine)).all()
    tree = []
    for d in dishes:
        children = [{"ingredient": ings[l.ingredient_id].name, "qty": l.qty_per_portion,
                     "unit": ings[l.ingredient_id].unit}
                    for l in lines if l.dish_id == d.id]
        tree.append({"dish": d.name, "code": d.code, "children": children})
    return tree
