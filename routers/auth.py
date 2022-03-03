import datetime as d
import os
import secrets
import smtplib
import ssl
from collections import namedtuple
from datetime import datetime
from datetime import timedelta
from email.message import EmailMessage
from typing import Optional

from fastapi import Depends
from fastapi import Header
from fastapi import HTTPException
from fastapi import status
from fastapi.security import OAuth2PasswordBearer
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt
from jose import JWTError
from passlib.hash import pbkdf2_sha256
from pydantic import BaseModel
from sqlalchemy import and_
from sqlalchemy.orm import Session

from . import get_db
from . import router
from database.models import User
from helpers.token_verification import generate_id_from_token
from helpers.token_verification import verify_id_from_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth")


# Schemas
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenPayload(BaseModel):
    id: Optional[str]


class UserAuth(BaseModel):
    email: str
    password: str
    is_active: Optional[bool]


class ForgotPassword(BaseModel):
    password: str
    otp: str

    class Config:
        orm_mode = True


class OtpEmail(BaseModel):
    email: str

    class Config:
        orm_mode = True


# Helpers


def get_password_hash(password: str):
    return pbkdf2_sha256.hash(password)


def verify_password(plain_password: str, password_hash: str):
    return pbkdf2_sha256.verify(plain_password, password_hash)


def find_user_by_email(email: str, db: Session = Depends(get_db)):
    return db.query(User).filter(User.email == email).first()


def authenticate_user(email: str, password: str, db: Session = Depends(get_db)):
    email = email.lower()
    user = find_user_by_email(email, db)

    if not user:
        raise HTTPException(
            status_code=401, detail="Sorry! We cannot find that email address"
        )
    if not verify_password(password, user.password):
        raise HTTPException(status_code=401, detail="Sorry! That password is incorrect")
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    # sourcery skip: inline-immediately-returned-variable
    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(
        minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
    )

    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(
        to_encode, os.getenv("SECRET_KEY"), algorithm=os.getenv("ALGORITHM")
    )
    return encoded_jwt


def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Sorry! We could not validate those credentials",
        headers={"WWWW-Authenticate": "Bearer"},
    )

    if not token:
        return HTTPException(
            status_code=401,
            detail="Could not verify your credentials",
            headers={"WWWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(token, os.getenv("SECRET_KEY"), os.getenv("ALGORITHM"))
        sub = payload.get("sub")
        token_data = TokenPayload(id=sub)
        if sub is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = (
        db.query(User.id, User.name, User.email, User.is_active, User.verify_user)
        .filter(and_(User.id == token_data.id))
        .first()
    )

    if user is None:
        raise credentials_exception

    CurrentUser = namedtuple(
        "CurrentUser",
        "id name email is_active verify_user",
    )

    user_dict = CurrentUser._make(user)._asdict()

    return {
        "id": user_dict["id"],
        "name": user_dict["name"],
        "email": user_dict["email"],
        "is_active": user_dict["is_active"],
        "verify_user": user_dict["verify_user"],
    }


def get_current_active_user(current_user: UserAuth = Depends(get_current_user)):
    if not current_user["is_active"]:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def fp_get_email(email: str, db: Session):
    return (
        db.query(User.id, User.email, User.otp_generation_timestamp)
        .filter(User.email == email.lower())
        .first()
    )


def fp_generate_otp(id: str, otp: str, db: Session):
    db.query(User).filter(User.id == id).update(
        {User.otp: otp, User.otp_generation_timestamp: datetime.now()}
    )
    db.commit()


def fp_validate_otp(otp: str, db: Session):
    return db.query(User).filter(User.otp == otp).first()


def fp_change_password(id: str, password: str, db: Session):
    db.query(User).filter(User.id == id).update({User.password: password})
    db.commit()


# End points
@router.post("/auth", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = authenticate_user(form_data.username, form_data.password, db)
    id = str(user.id)
    access_token = create_access_token(data={"sub": id})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/auth/current_user", status_code=status.HTTP_200_OK)
def get_current_user(
    current_user: UserAuth = Depends(get_current_active_user),
    authorization: str = Header(None),
):
    if not generate_id_from_token(authorization, current_user["id"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session Expired"
        )

    return current_user


@router.get("/token/verify", status_code=status.HTTP_200_OK)
def verify_token_validity(
    authorization: str = Header(None), db: Session = Depends(get_db)
):
    verification_status = verify_id_from_token(authorization, db)

    if not verification_status:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session Expired"
        )


@router.get("/email/{email}", status_code=status.HTTP_200_OK)
def verify_email_address(email: str, db: Session = Depends(get_db)):
    record = fp_get_email(email, db)

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="That email does not exist"
        )

    if (
        record.otp_generation_timestamp
        and datetime.now() < record.otp_generation_timestamp + d.timedelta(minutes=5)
    ):
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail="Please wait for 5 minutes before generating your next otp",
        )

    return record


@router.put("/otp/{id}", status_code=status.HTTP_201_CREATED)
def generate_otp(id: str, db: Session = Depends(get_db)):
    try:
        otp = secrets.token_hex(3).upper()

        fp_generate_otp(id, otp, db)
        return {"message": "Otp generated", "token": otp}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not generate the otp",
        )


@router.post("/email/send_otp", status_code=status.HTTP_201_CREATED)
def send_otp_to_user(otp: OtpEmail, db: Session = Depends(get_db)):
    record = db.query(User).filter(User.email == otp.email).first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="That email does not exist"
        )

    msg = EmailMessage()

    port = 465  # For SSL
    smtp_server = "smtp.gmail.com"
    password = os.getenv("SMTP_PASSWORD")

    msg["From"] = "rentorsale.apartments@gmail.com"
    msg["To"] = record.email
    msg["Subject"] = "OTP to reset your password"
    msg.set_content(
        f"Otp to reset your rentorsale.apartments password - {record.otp}.\n\nThe otp is valid for 10 minutes only."
    )

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
        server.login(msg["From"], password)
        server.send_message(msg)
        server.quit()

    return {"message": "Email sent"}


@router.put("/user/password/{id}", status_code=status.HTTP_201_CREATED)
def change_password(id: str, fp: ForgotPassword, db: Session = Depends(get_db)):
    record = db.query(User).filter(User.id == id).first()

    if datetime.now() > record.otp_generation_timestamp + d.timedelta(minutes=10):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Otp has expired"
        )

    if not fp_validate_otp(fp.otp, db):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect otp"
        )

    password = pbkdf2_sha256.hash(fp.password)

    fp_change_password(id, password, db)

    return {"message": "Password changed successfully"}
