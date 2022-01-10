import uuid
from datetime import date

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column
from sqlalchemy import String
from sqlalchemy import Date
from sqlalchemy import ForeignKey
from sqlalchemy import Boolean
from sqlalchemy.orm import relationship
from database.db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), nullable=False)
    email = Column(String(50), nullable=False, unique=True)
    password = Column(String(200), nullable=False)
    otp = Column(String(6))
    date_created = Column(Date, default=date.today)

    def __repr__(self) -> str:
        return f"User({self.email})"

class Apartment(Base):
    __tablename__ = "apartments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    address1 = Column(String(150), nullable=False)
    address2 = Column(String(150))
    city = Column(String(50))
    state = Column(String(50))
    pincode = Column(String(50))

    def __repr__(self) -> str:
        return f"Apartment({self.name})"

class Listing(Base):
    __tablename__ = "listings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(200), nullable=False)
    listing_type = Column(String(10), nullable=False)
    total_area = Column(String(10))
    description = Column(String(500), nullable=False)
    mobile_number = Column(String(15), nullable=False)
    bedrooms = Column(String(3), nullable=False)
    bathrooms = Column(String(3))
    floors = Column(String(3))
    whatsapp_number = Column(Boolean)
    parking_available = Column(Boolean)
    brokers_excuse = Column(Boolean)
    available_from = Column(String(10))
    user_id = Column(UUID, ForeignKey("users.id"))
    apartment_id = Column(UUID, ForeignKey("apartments.id"))
    date_created = Column(Date, default=date.today)

    user = relationship("User")
    apartment = relationship("Apartment")

    def __repr__(self) -> str:
        return f"Listing({self.title})"


class LisingImage(Base):

    __tablename__ = "listingimages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id = Column(UUID, ForeignKey("listings.id"))
    image_path = Column(String(200), nullable=False)

    listing = relationship("Listing")

    def __repr__(self) -> str:
        return f"ListingImage({self.listing_id}, {self.image_path})"