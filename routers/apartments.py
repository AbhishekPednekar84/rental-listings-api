from . import router
from database.models import Apartment
from sqlalchemy.orm import Session
from . import get_db
from fastapi import status
from fastapi import HTTPException
from fastapi import Depends
from pydantic import BaseModel
from typing import Optional, List


class ApartmentBase(BaseModel):
    name: str
    address1: str
    address2: Optional[str]
    city: str
    state: str
    pincode: str

    class Config:
        orm_mode = True


def get_all_apartments(db: Session):
    return db.query(Apartment).order_by(Apartment.name.desc()).all()


@router.get("/apartments", response_model=List[ApartmentBase], status_code=status.HTTP_200_OK)
async def get_apartments(db: Session = Depends(get_db)):
    """Returns a list of all the apartments

    Parameters
    ----------
    db : Session

    Returns
    -------
    List : the list is based on the ApartmentBase model 
        

    Raises
    ------
    HTTPException
        
    """
    try:
        return get_all_apartments(db)
    except Exception:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching apartments")

