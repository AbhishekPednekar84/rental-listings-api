from uuid import UUID


def uuid_validator(id: str):
    try:
        return bool(UUID(id))
    except ValueError:
        return False
