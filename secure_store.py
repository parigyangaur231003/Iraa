import base64, json, os
from cryptography.fernet import Fernet, InvalidToken

def _fernet():
    key = os.getenv("SECRET_KEY", "")
    if not key:
        raise RuntimeError("SECRET_KEY missing in .env")
    try:
        raw = base64.urlsafe_b64decode(key)
        if len(raw) != 32:
            raise ValueError
        k = base64.urlsafe_b64encode(raw)
    except Exception:
        k = key.encode()
    return Fernet(k)

def encrypt_json(obj: dict) -> bytes:
    data = json.dumps(obj, separators=(",",":")).encode()
    return _fernet().encrypt(data)

def decrypt_json(blob: bytes) -> dict:
    try:
        data = _fernet().decrypt(blob)
        return json.loads(data.decode())
    except (InvalidToken, ValueError):
        raise RuntimeError("Decryption failed")