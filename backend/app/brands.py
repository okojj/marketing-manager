from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth import current_user, require_origin
from app.db import get_db
from app.models import Brand, User

router = APIRouter(prefix="/api/brands", tags=["brands"])

class BrandInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    target_audience: str = Field(min_length=1, max_length=2000)
    tone: str = Field(min_length=1, max_length=100)

class BrandOutput(BrandInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime

def owned_brand(brand_id: int, db: Session, user: User) -> Brand:
    brand = db.scalar(select(Brand).where(Brand.id == brand_id, Brand.owner_id == user.id))
    if brand is None:
        raise HTTPException(404, "브랜드를 찾을 수 없습니다.")
    return brand

@router.get("", response_model=list[BrandOutput])
def list_brands(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return db.scalars(select(Brand).where(Brand.owner_id == user.id).order_by(Brand.id.desc())).all()

@router.get("/{brand_id}", response_model=BrandOutput)
def get_brand(brand_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return owned_brand(brand_id, db, user)

@router.post("", response_model=BrandOutput, status_code=201, dependencies=[Depends(require_origin)])
def create_brand(data: BrandInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    brand = Brand(**data.model_dump(), owner_id=user.id)
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand

@router.put("/{brand_id}", response_model=BrandOutput, dependencies=[Depends(require_origin)])
def update_brand(brand_id: int, data: BrandInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    brand = owned_brand(brand_id, db, user)
    for key, value in data.model_dump().items():
        setattr(brand, key, value)
    db.commit()
    db.refresh(brand)
    return brand

@router.delete("/{brand_id}", status_code=204, dependencies=[Depends(require_origin)])
def delete_brand(brand_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    db.delete(owned_brand(brand_id, db, user))
    db.commit()
    return Response(status_code=204)
