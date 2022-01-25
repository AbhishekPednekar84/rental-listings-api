from typing import List
from typing import Optional
from uuid import UUID

from fastapi import Header
from fastapi import HTTPException
from fastapi import status
from fastapi.param_functions import Depends
from passlib.hash import pbkdf2_sha256
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import get_db
from . import router
from .auth import create_access_token
from database.models import Apartment
from database.models import Listing
from database.models import ListingImage
from database.models import User
from helpers.token_verification import verify_id_from_token
from routers.listings import delete_selected_listing


class UserBase(BaseModel):
    id: Optional[UUID]
    name: str
    email: str

    class Config:
        orm_mode = True


class UserRegister(UserBase):
    password: str


class UserListing(BaseModel):
    title: str
    listing_type: str
    apartment: str

    class Config:
        orm_mode = True


class UserDashboard(BaseModel):
    count: int
    apartment: str

    class Config:
        orm_mode = True


class UserUpdate(BaseModel):
    id: UUID
    name: str

    class Config:
        orm_mode = True


def create_new_user(user: UserRegister, db: Session):
    new_user = User(
        name=user.name.title(),
        email=user.email.lower(),
        password=pbkdf2_sha256.hash(user.password),
    )

    db.add(new_user)
    db.commit()

    return new_user


def check_for_existing_email(email: str, db: Session):
    return db.query(User).filter(User.email == email.lower()).first()


def fetch_user_from_id(id: UUID, db: Session):
    return db.query(User).filter(User.id == id).first()


def get_listings_for_a_user(user_id: str, db: Session):
    return (
        db.query(
            Listing.id,
            Listing.title,
            Listing.listing_type,
            Apartment.name.label("apartment"),
        )
        .join(Apartment, Listing.apartment_id == Apartment.id)
        .filter(Listing.user_id == user_id)
        .all()
    )


def get_listing_images(listing_id, db):
    return (
        db.query(
            ListingImage.image_path,
            ListingImage.thumbnail_url,
            ListingImage.height,
            ListingImage.width,
        )
        .filter(ListingImage.listing_id == str(listing_id))
        .all()
    )


def get_dashboard_information_for_a_user(user_id: str, db: Session):
    return (
        db.query(
            func.count(Listing.user_id).label("count"),
            Apartment.name.label("apartment"),
        )
        .join(Apartment, Listing.apartment_id == Apartment.id)
        .filter(Listing.user_id == user_id)
        .group_by(Apartment.name)
        .all()
    )


def update_user_information(id: UUID, name: str, db: Session):
    db.query(User).filter(User.id == id).update({User.name: name})

    db.commit()

    return db.query(User.name, User.id, User.email).filter(User.id == id).first()


def delete_selected_user(user_id: str, db: Session):
    listing_ids = db.query(Listing.id).filter(Listing.user_id == user_id).all()

    if len(listing_ids) != 0:
        for id in listing_ids:
            delete_selected_listing(str(id[0]), db)

    db.query(User).filter(User.id == user_id).delete()

    db.commit()

    return "User deleted"


@router.post("/user", status_code=status.HTTP_201_CREATED)
def register_user(user: UserRegister, db: Session = Depends(get_db)):
    try:
        record = check_for_existing_email(user.email, db)
        if record:
            return {
                "message": f"{user.email} already exists. Please pick a different email address."
            }

        record = create_new_user(user, db)
        token = create_access_token(data={"sub": str(record.id)})

        return {
            "id": record.id,
            "name": record.name,
            "email": record.email,
            "token": token,
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not register user",
        )


@router.get("/user/{user_id}", response_model=UserBase, status_code=status.HTTP_200_OK)
def get_individual_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
):

    # Return None here since this call is happening serverside
    if not verify_id_from_token(authorization, db):
        return None

    try:
        return fetch_user_from_id(user_id, db) or None
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Could not fetch user"
        )


@router.put("/user/update", status_code=status.HTTP_201_CREATED)
def update_user_profile(
    user: UserUpdate,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    if not verify_id_from_token(authorization, db):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        )

    try:
        return update_user_information(user.id, user.name, db)

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not update your details",
        )


@router.get(
    "/user/listings/{user_id}",
    # response_model=List[UserListing],
    status_code=status.HTTP_200_OK,
)
def get_user_listings(user_id: str, db: Session = Depends(get_db)):
    try:
        image_list = []
        listings_list = []
        image_obj = {}
        listing_obj = {}

        listings = get_listings_for_a_user(user_id, db)

        if not listings:
            return []

        for listing in listings:

            listing_obj["id"] = listing.id
            listing_obj["title"] = listing.title
            listing_obj["listing_type"] = listing.listing_type
            listing_obj["apartment"] = listing.apartment

            images = get_listing_images(listing.id, db)

            if len(images) == 0:
                listing_obj["images"] = []

            for image in images:

                image_obj["image_url"] = image[0]
                image_obj["image_thumbnail"] = image[1]
                image_obj["height"] = image[2]
                image_obj["width"] = image[3]

                image_list.append(image_obj.copy())

                listing_obj["images"] = image_list

            listings_list.append(listing_obj.copy())

        return listings_list

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch all the listings for this user",
        )


@router.get(
    "/user/dashboard/{user_id}",
    response_model=List[UserDashboard],
    status_code=status.HTTP_200_OK,
)
def get_user_dashboard_data(user_id: str, db: Session = Depends(get_db)):
    try:
        return get_dashboard_information_for_a_user(user_id, db)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch all the listings for this user",
        )


@router.delete("/user/delete/{user_id}", status_code=status.HTTP_201_CREATED)
def delete_user(user_id: str, db: Session = Depends(get_db)):
    try:
        return delete_selected_user(user_id, db)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete user",
        )
