import io
import json
import os
import secrets
from typing import List
from typing import Optional
from uuid import UUID

from fastapi import Depends
from fastapi import Form
from fastapi import HTTPException
from fastapi import status
from fastapi import UploadFile
from PIL import Image
from PIL import UnidentifiedImageError
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import get_db
from . import router
from database.models import Apartment
from database.models import Listing
from database.models import ListingImage
from database.models import User
from helpers.imagekit_init import initialize_imagekit


class ListingBase(BaseModel):
    id: Optional[UUID]
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
    pets_available: Optional[bool]
    brokers_excuse: Optional[bool]
    available_from: str
    user_id: UUID
    apartment_id: UUID
    apartment: Optional[str]
    images: Optional[List[str]]

    class Config:
        orm_mode = True


def uuid_validator(id: str):
    try:
        return bool(UUID(id))
    except ValueError:
        return False


def get_all_listings(db: Session):
    return db.query(Listing).order_by(Listing.date_created.desc()).all()


def get_listing(listing_id: UUID, db: Session):
    return (
        db.query(
            Listing.title,
            Listing.listing_type,
            Listing.total_area,
            Listing.description,
            Listing.mobile_number,
            Listing.bedrooms,
            Listing.bathrooms,
            Listing.floors,
            Listing.whatsapp_number,
            Listing.parking_available,
            Listing.pets_allowed,
            Listing.brokers_excuse,
            Listing.available_from,
            Listing.user_id,
            Listing.apartment_id,
            Listing.date_created,
            Apartment.name.label("apartment"),
            User.name.label("user_name"),
        )
        .join(Apartment, Listing.apartment_id == Apartment.id)
        .join(User, Listing.user_id == User.id)
        .filter(Listing.id == listing_id)
        .first()
    )


def get_listing_images(listing_id, db):
    images = (
        db.query(
            ListingImage.image_path,
            ListingImage.thumbnail_url,
            ListingImage.height,
            ListingImage.width,
            ListingImage.imagekit_file_id,
        )
        .filter(ListingImage.listing_id == str(listing_id))
        .all()
    )

    image_list = []
    image_obj = {}

    if len(images) > 0:
        for image in images:
            image_obj["image_url"] = image[0]
            image_obj["image_thumbnail"] = image[1]
            image_obj["height"] = image[2]
            image_obj["width"] = image[3]
            image_obj["ik_file_id"] = image[4]

            image_list.append(image_obj.copy())

    return image_list


def get_listings_for_apartment(apartment: str, db: Session):
    return (
        db.query(Listing)
        .join(Apartment, Listing.apartment_id == Apartment.id)
        .filter(Apartment.name == apartment)
        .all()
    )


def filter_listings(rent, sale, bedrooms, apartment, db: Session):
    filter = db.query(
        Listing.id,
        Listing.title,
        Listing.listing_type,
        Listing.total_area,
        Listing.description,
        Listing.mobile_number,
        Listing.bedrooms,
        Listing.bathrooms,
        Listing.floors,
        Listing.whatsapp_number,
        Listing.parking_available,
        Listing.brokers_excuse,
        Listing.available_from,
        Listing.user_id,
        Listing.apartment_id,
        Listing.date_created,
        Apartment.name.label("apartment"),
    ).join(Apartment, Listing.apartment_id == Apartment.id)

    if rent and sale:
        filter = filter.filter(
            Listing.listing_type == "rent" and Listing.listing_type == "sale"
        )
    elif rent:
        filter = filter.filter(Listing.listing_type == "rent")
    elif sale:
        filter = filter.filter(Listing.listing_type == "sale")

    if bedrooms:
        if bedrooms == "3+":
            filter = filter.filter(Listing.bedrooms > 3)
        else:
            filter = filter.filter(Listing.bedrooms == int(bedrooms))

    filter = filter.filter(Apartment.name == apartment)

    return filter.all()


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
        apartment_id=str(listing.apartment_id),
    )

    db.add(new_listing)
    db.commit()

    return new_listing.id


def create_image_record(
    listing_id: UUID,
    image_path: str,
    height: int,
    width: int,
    thumbnailUrl: str,
    ik_fileId: str,
    db: Session,
):
    new_image = ListingImage(
        listing_id=str(listing_id),
        image_path=image_path,
        height=height,
        width=width,
        imagekit_file_id=ik_fileId,
        thumbnail_url=thumbnailUrl,
    )

    db.add(new_image)
    db.commit()


def upload_image_to_imagekit(listing_id: str, images: List, db: Session):
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
                    "folder": f"Listings/ads/{listing_id}",
                    "is_private_file": False,
                    "use_unique_file_name": False,
                },
            )

            create_image_record(
                listing_id,
                uploaded_image["response"]["url"],
                uploaded_image["response"]["height"],
                uploaded_image["response"]["width"],
                uploaded_image["response"]["thumbnailUrl"],
                uploaded_image["response"]["fileId"],
                db,
            )
        except UnidentifiedImageError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The format of the uploaded image is currently unsupported.\nPlease upload a different image.",
            )


def delete_selected_listing(listing_id: str, db: Session):
    listing_images = (
        db.query(ListingImage.imagekit_file_id)
        .filter(ListingImage.listing_id == listing_id)
        .all()
    )

    if len(listing_images) > 0:
        imagekit = initialize_imagekit()

        for image in listing_images:
            imagekit.delete_file(image)

        db.query(ListingImage).filter(ListingImage.listing_id == listing_id).delete()
        db.commit()

    db.query(Listing).filter(Listing.id == listing_id).delete()
    db.commit()


@router.get(
    "/listings", response_model=List[ListingBase], status_code=status.HTTP_200_OK
)
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch listings",
        )


@router.get("/listings/{listing_id}", status_code=status.HTTP_200_OK)
def get_single_listing(listing_id: str, db: Session = Depends(get_db)):
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
        if not uuid_validator(listing_id):
            return []

        listing = get_listing(listing_id, db)

        if not listing:
            return []

        images = get_listing_images(listing_id, db)

        return {
            "title": listing.title,
            "listing_type": listing.listing_type,
            "total_area": listing.total_area,
            "description": listing.description,
            "mobile_number": listing.mobile_number,
            "bedrooms": listing.bedrooms,
            "bathrooms": listing.bathrooms,
            "floors": listing.floors,
            "whatsapp_number": listing.whatsapp_number,
            "parking_available": listing.parking_available,
            "pets_allowed": listing.pets_allowed,
            "brokers_excuse": listing.brokers_excuse,
            "available_from": listing.available_from,
            "user_id": listing.user_id,
            "apartment_id": listing.apartment_id,
            "apartment": listing.apartment,
            "user_name": listing.user_name,
            "date_created": listing.date_created,
            "images": images,
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch the listing",
        )


@router.post("/listings", status_code=status.HTTP_201_CREATED)
def create_listing(
    title: str = Form(...),
    listing_type: str = Form(...),
    total_area: Optional[str] = Form(...),
    description: str = Form(...),
    mobile_number: str = Form(...),
    bedrooms: str = Form(...),
    bathrooms: Optional[str] = Form(...),
    floors: Optional[str] = Form(...),
    whatsapp_number: Optional[bool] = Form(...),
    parking_available: Optional[bool] = Form(...),
    pets_allowed: Optional[bool] = Form(...),
    brokers_excuse: Optional[bool] = Form(...),
    available_from: str = Form(...),
    user_id: UUID = Form(...),
    apartment_id: UUID = Form(...),
    images: Optional[List[UploadFile]] = Form([]),
    db: Session = Depends(get_db),
):
    try:
        new_listing = Listing(
            title=title,
            listing_type=listing_type,
            total_area=total_area,
            description=description,
            mobile_number=mobile_number,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            floors=floors,
            whatsapp_number=whatsapp_number,
            parking_available=parking_available,
            pets_allowed=pets_allowed,
            brokers_excuse=brokers_excuse,
            available_from=available_from,
            user_id=str(user_id),
            apartment_id=str(apartment_id),
        )

        db.add(new_listing)
        db.commit()

        if new_listing.id and images:
            upload_image_to_imagekit(new_listing.id, images, db)

        return new_listing.id

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create listing",
        )


@router.put("/listings", status_code=status.HTTP_201_CREATED)
def update_listing(
    listing_id: str = Form(...),
    title: str = Form(...),
    listing_type: str = Form(...),
    total_area: Optional[str] = Form(...),
    description: str = Form(...),
    mobile_number: str = Form(...),
    bedrooms: str = Form(...),
    bathrooms: Optional[str] = Form(...),
    floors: Optional[str] = Form(...),
    whatsapp_number: Optional[bool] = Form(...),
    parking_available: Optional[bool] = Form(...),
    pets_allowed: Optional[bool] = Form(...),
    brokers_excuse: Optional[bool] = Form(...),
    available_from: str = Form(...),
    images: Optional[List[UploadFile]] = Form([]),
    db: Session = Depends(get_db),
):
    try:
        db.query(Listing).filter(Listing.id == listing_id).update(
            {
                Listing.title: title,
                Listing.listing_type: listing_type,
                Listing.total_area: total_area,
                Listing.description: description,
                Listing.mobile_number: mobile_number,
                Listing.bedrooms: bedrooms,
                Listing.bathrooms: bathrooms,
                Listing.floors: floors,
                Listing.whatsapp_number: whatsapp_number,
                Listing.parking_available: parking_available,
                Listing.pets_allowed: pets_allowed,
                Listing.brokers_excuse: brokers_excuse,
                Listing.available_from: available_from,
            }
        )

        db.commit()

        if images:
            upload_image_to_imagekit(listing_id, images, db)

        return listing_id

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create listing",
        )


@router.delete("/listing/{listing_id}", status_code=status.HTTP_201_CREATED)
def delete_listing(listing_id: str, db: Session = Depends(get_db)):
    try:
        delete_selected_listing(listing_id, db)

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete listing",
        )


@router.get("/listings/apartment/{apartment}", status_code=status.HTTP_200_OK)
def get_all_listings_for_apartment(apartment: str, db: Session = Depends(get_db)):
    """
    Returns a single listing

    Parameters
    ----------
    db : Session

    Returns
    -------
    Data for a single apartment based on the ListingBase model

    Raises
    ------
    HTTPException

    """
    try:
        records = get_listings_for_apartment(apartment, db)

        listings = []
        single_listing = {}

        # images = get_listing_images(record.id, db)

        # print(images)

        for record in records:
            image_list = get_listing_images(record.id, db)

            single_listing["id"] = record.id
            single_listing["title"] = record.title
            single_listing["listing_type"] = record.listing_type
            single_listing["description"] = record.description
            single_listing["bedrooms"] = record.bedrooms
            single_listing["date_created"] = record.date_created
            single_listing["images"] = image_list

            listings.append(single_listing.copy())

        return listings
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch the listing",
        )


@router.get(
    "/listings/filter/{listing_filter}/{apartment}", status_code=status.HTTP_200_OK
)
def filter_listings_for_apartment(
    listing_filter: str, apartment: str, db: Session = Depends(get_db)
):
    """
    Returns listings for an apartment based on the filter

    Parameters
    ----------
    listing_filter : str
    apartment : str
    db : Session, optional

    Returns
    -------
    List

    Raises
    ------
    HTTPException
    """
    try:
        filtered_results = []
        filtered_result_obj = {}

        filters_dict = json.loads(listing_filter)

        rent = filters_dict["rent"]
        sale = filters_dict["sale"]
        bedrooms = filters_dict["bedrooms"]

        if not rent and not sale and not bedrooms:
            return get_listings_for_apartment(apartment, db)

        records = filter_listings(rent, sale, bedrooms, apartment, db)

        for record in records:
            images = get_listing_images(record.id, db)
            filtered_result_obj["id"] = record.id
            filtered_result_obj["title"] = record.title
            filtered_result_obj["listing_type"] = record.listing_type
            filtered_result_obj["description"] = record.description
            filtered_result_obj["bedrooms"] = record.bedrooms
            filtered_result_obj["date_created"] = record.date_created
            filtered_result_obj["images"] = images
            filtered_results.append(filtered_result_obj.copy())

        return filtered_results

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch the listing",
        )


@router.delete("/image/{file_id}", status_code=status.HTTP_201_CREATED)
def remove_image_from_imagekit(file_id: str, db: Session = Depends(get_db)):
    imagekit = initialize_imagekit()

    delete_image = imagekit.delete_file(file_id)

    if not delete_image["error"]:
        db.query(ListingImage).filter(ListingImage.imagekit_file_id == file_id).delete()
        db.commit()
