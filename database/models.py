import uuid
from datetime import date

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Date
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql.sqltypes import DateTime

from database.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), nullable=False)
    email = Column(String(50), nullable=False, unique=True)
    password = Column(String(200), nullable=False)
    otp = Column(String(6))
    otp_generation_timestamp = Column(DateTime)
    is_active = Column(Boolean, default=True)
    date_created = Column(Date, default=date.today)
    verify_user = Column(Boolean, default=False)
    verification_email_resend_count = Column(Integer, default=0)

    def __repr__(self) -> str:
        return f"User({self.email})"


class Apartment(Base):
    __tablename__ = "apartments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    address1 = Column(String(150))
    address2 = Column(String(150))
    city = Column(String(50))
    state = Column(String(50))
    pincode = Column(String(50), nullable=False)
    name_token = Column(TSVECTOR)

    def __repr__(self) -> str:
        return f"Apartment({self.name})"


class Listing(Base):
    __tablename__ = "listings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(200), nullable=False)
    listing_type = Column(String(10), nullable=False)
    total_area = Column(Float)
    description = Column(String(500))
    mobile_number = Column(String(15), nullable=False)
    bedrooms = Column(Integer, nullable=False)
    bathrooms = Column(Integer)
    floors = Column(Integer)
    whatsapp_number = Column(Boolean)
    parking_available = Column(Boolean)
    brokers_excuse = Column(Boolean)
    pets_allowed = Column(Boolean)
    available_from = Column(String(10))
    user_id = Column(UUID, ForeignKey("users.id"))
    apartment_id = Column(UUID, ForeignKey("apartments.id"))
    date_created = Column(Date, default=date.today)
    rent_amount = Column(Float)
    maintenance_amount = Column(Float)
    deposit_amount = Column(Float)
    sale_amount = Column(Float)
    sale_amount_value = Column(String(50), default="Lakhs")
    maintenance_included_in_rent = Column(Boolean)
    rent_amount_negotiable = Column(Boolean)
    sale_amount_negotiable = Column(Boolean)
    facing_direction = Column(String(50))
    non_vegetarians = Column(Boolean)
    tenant_preference = Column(String(250))
    total_floors = Column(Integer)
    prefers_call = Column(Boolean)
    prefers_text = Column(Boolean)

    user = relationship("User")
    apartment = relationship("Apartment")

    def __repr__(self) -> str:
        return f"Listing({self.title})"


class ListingImage(Base):

    __tablename__ = "listingimages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id = Column(UUID, ForeignKey("listings.id"))
    imagekit_file_id = Column(String(100))
    image_path = Column(String(200), nullable=False)
    height = Column(Integer)
    width = Column(Integer)
    thumbnail_url = Column(String(200))

    listing = relationship("Listing")

    def __repr__(self) -> str:
        return f"ListingImage({self.listing_id}, {self.image_path})"
