import io
import secrets
import os

from uuid import UUID
from . import router
from . import get_db
from sqlalchemy.orm import Session
from database.models import Listing
from fastapi import status
from fastapi import HTTPException
from fastapi import Depends
from pydantic import BaseModel
from typing import Optional
from typing import List
from helpers.imagekit_init import initialize_imagekit
from PIL import Image
from PIL import UnidentifiedImageError

class ListingBase(BaseModel):
    title: str
    listing_type: str
    total_area: Optional[str]
    description: str
    mobile_number: str
    bedrooms: str
    bathrooms: Optional[str]
    floors: Optional[str]
    whatsapp_number: Optional[bool]
    parking_available: Optional[bool]
    brokers_excuse: Optional[bool]
    available_from: str
    user_id: UUID
    apartment_id: UUID

    class Config:
        orm_mode = True


def get_all_listings(db: Session):
    return db.query(Listing).order_by(Listing.date_created.desc()).all()


def get_listing(listing_id: UUID, db: Session):
    return db.query(Listing).filter(Listing.id == listing_id).first()

def create_new_listing(listing: ListingBase, db: Session):
    new_listing = Listing(
        title=listing.title,
        listing_type=listing.listing_type,
        total_area=listing.total_area,
        description=listing.description,
        mobile_number=listing.mobile_number,
        bedrooms=listing.bedrooms,
        bathrooms=listing.bathrooms,
        floors=listing.floors,
        whatsapp_number=listing.whatsapp_number,
        parking_available=listing.parking_available,
        brokers_excuse=listing.brokers_excuse,
        available_from=listing.available_from,
        user_id=str(listing.user_id),
        apartment_id=str(listing.apartment_id)
    )

    db.add(new_listing)
    db.commit()

    return new_listing.id

def upload_image_to_imagekit(listing_id: str, images: List):
    imagekit = initialize_imagekit()

    for image in images:
        file_name, file_ext = os.path.splitext(image.filename)

        file_ext = file_ext.lower()

        if file_ext == ".jpg":
            file_ext = ".jpeg"

        try:
            optimized_image = Image.open(image.file)
            # optimized_image = fix_image_orientation(optimized_image)

            in_mem_file = io.BytesIO()
            optimized_image.save(in_mem_file, format=file_ext[1:], optimized=True)
            in_mem_file.seek(0)

            random_file_name = secrets.token_hex(8)

            uploaded_image = imagekit.upload_file(
                file=in_mem_file,
                file_name=random_file_name,
                options={
                    "folder": f"{listing_id}",
                    "is_private_file": False,
                    "use_unique_file_name": False,
                },
            )

            return uploaded_image["response"]["url"]
        except UnidentifiedImageError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The format of the uploaded image is currently unsupported.\nPlease upload a different image.",
            )


@router.get("/listings", response_model=List[ListingBase], status_code=status.HTTP_200_OK)
def get_listings(db: Session = Depends(get_db)):
    """
    Return all the listings in the database

    Parameters
    ----------
    db : Session

    Returns
    -------
    List : the list is based on the ListingBase model 

    Raises
    ------
    HTTPException
        
    """
    try:
        return get_all_listings(db)
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not fetch listings")


@router.get("/listings/{listing_id}", response_model=ListingBase, status_code=status.HTTP_200_OK)
def get_single_listing(listing_id: UUID, db: Session = Depends(get_db)):
    """
    Returns a single listing

    Parameters
    ----------
    db : Session

    Returns
    -------
    Data based on the ListingBase model 

    Raises
    ------
    HTTPException
        
    """
    try:
        return get_listing(listing_id, db)
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not fetch the listing")


@router.post("/listings", status_code=status.HTTP_201_CREATED)
def create_listing(listing: ListingBase, db: Session = Depends(get_db)):
    try:
        listing_id = create_new_listing(listing, db)

        if listing_id:
            upload_image_to_imagekit(listing_id, images)

    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create listing")
    