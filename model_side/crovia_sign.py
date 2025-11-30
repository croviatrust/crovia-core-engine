# crovia_sign.py
import hmac, hashlib, json, os

def hmac_sign(obj: dict, secret: str) -> str:
    msg = json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
