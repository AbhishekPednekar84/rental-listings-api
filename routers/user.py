from fastapi.param_functions import Depends
from . import router
from . import get_db
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import status
from fastapi import HTTPException
from pydantic import BaseModel
from database.models import User
from database.models import Listing
from database.models import Apartment
from passlib.hash import pbkdf2_sha256
from typing import List
from uuid import UUID


class UserBase(BaseModel):
    name: str
    email: str
    
    class Config: 
        orm_mode=True

class UserRegister(UserBase):
    password: str

class UserListing(BaseModel):
    title: str
    listing_type: str
    apartment: str

    class Config:
        orm_mode=True

class UserDashboard(BaseModel):
    count: int
    apartment: str

    class Config:
        orm_mode=True


def create_new_user(user: UserRegister, db: Session):
    new_user = User(
        name=user.name.title(),
        email=user.email.lower(),
        password=pbkdf2_sha256.hash(user.password)  
    )

    db.add(new_user)
    db.commit()

    return new_user.id


def check_for_existing_email(email: str, db: Session):
    return db.query(User).filter(User.email == email.lower()).first()


def get_listings_for_a_user(user_id: str, db: Session):
    return db.query(func.count(Listing.user_id), Listing.title, Listing.listing_type, Apartment.name.label( "apartment")).join(Apartment, Listing.apartment_id == Apartment.id).filter(Listing.user_id == user_id).group_by(Listing.title, Listing.listing_type, Apartment.name).all()


def get_dashboard_information_for_a_user(user_id: str, db: Session):
    return db.query(func.count(Listing.user_id).label("count"), Apartment.name.label("apartment")).join(Apartment, Listing.apartment_id == Apartment.id).filter(Listing.user_id == user_id).group_by(Apartment.name).all()


@router.post("/user", status_code=status.HTTP_201_CREATED)
def register_user(user: UserRegister, db: Session = Depends(get_db)):
    try:
        record = check_for_existing_email(user.email, db)
        if record:
            return {"message": f"{user.email} already exists. Please pick a different email address."}
            
        return create_new_user(user, db)
        
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not register user")


@router.get("/user/listings/{user_id}", response_model=List[UserListing], status_code=status.HTTP_200_OK)
def get_user_listings(user_id: str, db: Session = Depends(get_db)):
    try:
        return get_listings_for_a_user(user_id, db)
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not fetch all the listings for this user")


@router.get("/user/dashboard/{user_id}", response_model=List[UserDashboard], status_code=status.HTTP_200_OK)
def get_user_listings(user_id: str, db: Session = Depends(get_db)):
    try:
        return get_dashboard_information_for_a_user(user_id, db)
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not fetch all the listings for this user")

    