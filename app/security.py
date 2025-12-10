import base64
import hmac
import hashlib
import json
import time
from typing import Tuple, Optional

from app.config import env

SECRET_KEY = env("AUTH_SECRET", "dev-secret")
ACCESS_TTL_SECONDS = 3600
REFRESH_TTL_SECONDS = 3600 * 24 * 7


def _sign(payload: dict) -> str:
    data = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    sig = hmac.new(SECRET_KEY.encode("utf-8"), data.encode("utf-8"), hashlib.sha256).digest()
    token = base64.urlsafe_b64encode(data.encode("utf-8")).decode("utf-8") + "." + base64.urlsafe_b64encode(sig).decode("utf-8")
    return token


def _verify(token: str) -> Optional[dict]:
    if "." not in token:
        return None
    raw, sig_b64 = token.split(".", 1)
    try:
        data = base64.urlsafe_b64decode(raw.encode("utf-8"))
        sig = base64.urlsafe_b64decode(sig_b64.encode("utf-8"))
    except Exception:
        return None
    expected = hmac.new(SECRET_KEY.encode("utf-8"), data, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        payload = json.loads(data.decode("utf-8"))
    except Exception:
        return None
    return payload


def create_tokens(email: str) -> Tuple[str, int, str, int]:
    now = int(time.time())
    access_payload = {"sub": email, "exp": now + ACCESS_TTL_SECONDS}
    refresh_payload = {"sub": email, "exp": now + REFRESH_TTL_SECONDS, "type": "refresh"}
    access_token = _sign(access_payload)
    refresh_token = _sign(refresh_payload)
    return access_token, access_payload["exp"], refresh_token, refresh_payload["exp"]


def verify_access_token(token: str) -> Optional[str]:
    payload = _verify(token)
    if not payload or payload.get("sub") is None:
        return None
    exp = payload.get("exp")
    if exp is not None and int(time.time()) > int(exp):
        return None
    return payload["sub"]
