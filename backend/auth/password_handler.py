import bcrypt


def _bcrypt_password_bytes(password: str) -> bytes:
    # bcrypt processes up to 72 bytes; mirror that behavior consistently.
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    password_bytes = _bcrypt_password_bytes(password)
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    plain_bytes = _bcrypt_password_bytes(plain_password)
    return bcrypt.checkpw(plain_bytes, hashed_password.encode("utf-8"))
