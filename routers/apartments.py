import json
import os
import sys
from typing import List
from typing import Optional
from uuid import UUID

import requests
from fastapi import BackgroundTasks
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import get_db
from . import router
from database.models import Apartment
from helpers.stop_words import stop_words


class ApartmentBase(BaseModel):
    id: UUID
    name: str
    address1: Optional[str]
    address2: Optional[str]
    city: Optional[str]
    state: Optional[str]
    pincode: Optional[str]

    class Config:
        orm_mode = True


class ApartmentCreate(BaseModel):
    name: str
    pincode: str

    class Config:
        orm_mode = True


class ApartmentSearch(BaseModel):
    name: str
    city: str
    pincode: str

    class Config:
        orm_mode = True


def get_all_apartments(db: Session):
    return db.query(Apartment).order_by(Apartment.name).all()


def get_specific_apartment(apartment: str, db: Session):
    return db.query(Apartment).filter(Apartment.name == apartment).first()


def get_specific_apartment_from_id(apartment_id: str, db: Session):
    return db.query(Apartment).filter(Apartment.id == apartment_id).first()


def send_slack_message(apartment_name, pincode, city):
    url = os.getenv("SLACK_WEBHOOK_URL")
    message = f"The apartment {apartment_name.upper()} located in {city} ({pincode}) was just added"
    title = "New Apartment Added :zap:"
    slack_data = {
        "username": "ROSNotificationBot",
        "icon_emoji": ":satellite:",
        "attachments": [
            {
                "color": "#0D9488",
                "fields": [
                    {
                        "title": title,
                        "value": message,
                        "short": "false",
                    }
                ],
                "image_url": os.getenv("SLACK_ROS_IMAGE_URL"),
            }
        ],
    }
    byte_length = str(sys.getsizeof(slack_data))
    headers = {"Content-Type": "application/json", "Content-Length": byte_length}
    response = requests.post(url, data=json.dumps(slack_data), headers=headers)
    if response.status_code != 200:
        raise Exception(response.status_code, response.text)


@router.get(
    "/apartments", response_model=List[ApartmentBase], status_code=status.HTTP_200_OK
)
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
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching apartments"
        )


@router.get(
    "/apartment/{apartment}",
    response_model=ApartmentBase,
    status_code=status.HTTP_200_OK,
)
async def get_apartment(apartment: str, db: Session = Depends(get_db)):
    """Returns details of a specific apartment

    Parameters
    ----------
    db : Session

    Returns
    -------
    Dict : the dict is based on the ApartmentBase model


    Raises
    ------
    HTTPException

    """
    try:
        return get_specific_apartment(apartment, db)
    except Exception:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching apartments"
        )


@router.get(
    "/apartment/id/{apartment_id}",
    response_model=ApartmentBase,
    status_code=status.HTTP_200_OK,
)
async def get_apartment_from_id(apartment_id: str, db: Session = Depends(get_db)):
    """Returns details of a specific apartment based on the id

    Parameters
    ----------
    db : Session

    Returns
    -------
    Dict : the dict is based on the ApartmentBase model


    Raises
    ------
    HTTPException

    """
    try:
        return get_specific_apartment_from_id(apartment_id, db)
    except Exception:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching apartments"
        )


@router.post("/apartment", status_code=status.HTTP_201_CREATED)
def create_new_apartment(
    apartment: ApartmentCreate,
    background_task: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        res = requests.get(
            f"https://api.postalpincode.in/pincode/{apartment.pincode}"
        ).json()

        status = res[0]["Status"]

        if status == "Success":
            city = res[0]["PostOffice"][0]["District"]
        else:
            city = "City not found"

        new_apartment = Apartment(
            name=apartment.name.title(), city=city, pincode=apartment.pincode
        )

        db.add(new_apartment)
        db.commit()

        db.query(Apartment).filter(Apartment.id == new_apartment.id).update(
            {Apartment.name_token: func.to_tsvector(new_apartment.name)}
        )

        db.commit()

        background_task.add_task(
            send_slack_message, apartment.name, apartment.pincode, city
        )

        return {"id": new_apartment.id, "name": new_apartment.name}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create the apartment record",
        )


@router.get(
    "/search/apartment",
    response_model=List[ApartmentSearch],
    status_code=status.HTTP_200_OK,
)
def search_apartments(name: str, pincode: str, db: Session = Depends(get_db)):
    try:
        if not name:
            return None

        search_string = name.split(" ")

        if len(search_string) > 1:
            for word in search_string:
                if word in stop_words:
                    search_string.remove(word)

        if len(search_string) == 1:
            records = (
                db.query(Apartment)
                .filter(
                    Apartment.name_token.match(f"{search_string[0][:3]}:*"),
                    Apartment.pincode == pincode,
                )
                .all()
            )

        else:
            records = (
                db.query(Apartment)
                .filter(
                    Apartment.name_token.match(f"{search_string[1][:3]}:*"),
                    Apartment.pincode == pincode,
                )
                .all()
            )

        if not records:
            return []

        for record in records:
            return [
                {"name": record.name, "city": record.city, "pincode": record.pincode}
                for record in records
            ]

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not search apartments",
        )
