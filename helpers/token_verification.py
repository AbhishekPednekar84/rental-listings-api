import os
from datetime import datetime

from jose import jwt
from jose.exceptions import ExpiredSignatureError
from sqlalchemy.orm import Session

from database.models import User


def decode_token(token: str):
    if "Bearer" not in token:
        return False

    decoded_token = token.split(" ")

    decoded_token = jwt.decode(
        decoded_token[1], os.getenv("SECRET_KEY"), os.getenv("ALGORITHM")
    )

    return decoded_token


def generate_id_from_token(token: str, user_id: str):

    try:
        decoded_token = decode_token(token)
    except ExpiredSignatureError:
        return False

    has_token_expired = datetime.utcnow() > datetime.fromtimestamp(decoded_token["exp"])

    return decoded_token["sub"] == str(user_id) and not has_token_expired


def verify_id_from_token(token: str, db: Session):
    try:
        decoded_token = decode_token(token)
    except ExpiredSignatureError:
        return False

    has_token_expired = datetime.utcnow() > datetime.fromtimestamp(decoded_token["exp"])

    if has_token_expired:
        return False

    saved_id = db.query(User).filter(User.id == decoded_token["sub"]).first()

    return bool(saved_id)
